"""FastAPI dependency providers: settings, caller, session, repositories, services."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from functools import cache
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from minio import Minio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.auth.entities import Principal
from src.domain.auth.hasher import PasswordHasher
from src.domain.auth.service import AuthService
from src.domain.chunks.service import ChunkService
from src.domain.documents.service import DocumentService
from src.domain.tenants.service import TenantService
from src.domain.users.service import UserService
from src.infrastructure.database.postgres.repositories.chunk import (
    PostgresChunkRepository,
)
from src.infrastructure.database.postgres.repositories.document import (
    PostgresDocumentRepository,
)
from src.infrastructure.database.postgres.repositories.tenant import (
    PostgresTenantRepository,
)
from src.infrastructure.database.postgres.repositories.user import (
    PostgresUserRepository,
)
from src.infrastructure.database.postgres.session import get_db_session
from src.infrastructure.security.passwords import Argon2PasswordHasher
from src.infrastructure.security.tokens import decode_access_token
from src.infrastructure.storage.minio.storage import MinioStorage
from src.infrastructure.storage.service import create_storage_service
from src.libs.core.config import Settings, get_settings
from src.libs.exceptions.exceptions import (
    AuthenticationException,
    PermissionDeniedException,
)

SettingsDep = Annotated[Settings, Depends(get_settings)]
# scope="function" commits before the response is sent, so a failed commit returns 500.
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session, scope="function")]

# auto_error=False: a missing token raises AuthenticationException, so the 401 has
# the same error body as every other error.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{get_settings().api_prefix}/auth/token", auto_error=False
)


@cache
def get_password_hasher() -> PasswordHasher:
    """One hasher per process (it caches its dummy hash)."""
    return Argon2PasswordHasher()


HasherDep = Annotated[PasswordHasher, Depends(get_password_hasher)]


def get_minio_client(request: Request) -> Minio:
    """Return the MinIO client that the app created at startup (one per process)."""
    return request.app.state.storage_client


def get_minio_provider(
    settings: SettingsDep, client: Annotated[Minio, Depends(get_minio_client)]
) -> MinioStorage:
    return create_storage_service(client, settings)


type ReadinessProbe = Callable[[], Awaitable[None]]


def get_readiness_probes(
    request: Request,
    storage: Annotated[MinioStorage, Depends(get_minio_provider)],
) -> dict[str, ReadinessProbe]:
    """Return one probe per dependency that the API needs to serve requests.

    A probe returns when its dependency answers and raises when it does not.
    """

    async def database() -> None:
        async with request.app.state.db_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def object_storage() -> None:
        await asyncio.to_thread(storage.check_available)

    return {"database": database, "storage": object_storage}


def get_tenant_repository(session: DbSessionDep) -> PostgresTenantRepository:
    return PostgresTenantRepository(session=session)


def get_user_repository(session: DbSessionDep) -> PostgresUserRepository:
    return PostgresUserRepository(session=session)


def get_document_repository(session: DbSessionDep) -> PostgresDocumentRepository:
    return PostgresDocumentRepository(session=session)


def get_chunk_repository(session: DbSessionDep) -> PostgresChunkRepository:
    return PostgresChunkRepository(session=session)


def get_document_service(
    doc_repository: Annotated[
        PostgresDocumentRepository, Depends(get_document_repository)
    ],
    storage: Annotated[MinioStorage, Depends(get_minio_provider)],
) -> DocumentService:
    return DocumentService(doc_repository=doc_repository, storage=storage)


def get_tenant_service(
    repository: Annotated[PostgresTenantRepository, Depends(get_tenant_repository)],
) -> TenantService:
    return TenantService(repository=repository)


def get_user_service(
    user_repository: Annotated[PostgresUserRepository, Depends(get_user_repository)],
    hasher: HasherDep,
) -> UserService:
    return UserService(user_repository=user_repository, hasher=hasher)


def get_auth_service(
    user_repository: Annotated[PostgresUserRepository, Depends(get_user_repository)],
    hasher: HasherDep,
) -> AuthService:
    return AuthService(user_repository=user_repository, hasher=hasher)


async def get_current_principal(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    settings: SettingsDep,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> Principal:
    """Return the caller of the request.

    Raise AuthenticationException (401) if the bearer token is missing or invalid,
    or if its user no longer exists or is disabled.
    """
    if not token:
        raise AuthenticationException("The request has no bearer token.")
    user_id, tenant_id = decode_access_token(token, settings)
    return await auth_service.resolve(user_id, tenant_id)


PrincipalDep = Annotated[Principal, Depends(get_current_principal)]


async def get_current_tenant_id(principal: PrincipalDep) -> uuid.UUID:
    """Return the caller's tenant. Every tenant-scoped query uses it."""
    return principal.tenant_id


def require_admin(principal: PrincipalDep) -> Principal:
    """Return the caller. Raise PermissionDeniedException (403) if it is not admin."""
    if not principal.is_admin:
        raise PermissionDeniedException(f"User {principal.user_id} is not an admin.")
    return principal


def get_chunk_service(
    doc_repository: Annotated[
        PostgresDocumentRepository, Depends(get_document_repository)
    ],
    chunk_repository: Annotated[PostgresChunkRepository, Depends(get_chunk_repository)],
) -> ChunkService:
    return ChunkService(
        doc_repository=doc_repository, chunk_repository=chunk_repository
    )
