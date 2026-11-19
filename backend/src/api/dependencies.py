"""FastAPI dependency providers: settings, request session, repositories and services."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from minio import Minio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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
from src.infrastructure.storage.client import create_storage_client
from src.infrastructure.storage.minio.storage import MinioStorage
from src.infrastructure.storage.service import create_storage_service
from src.libs.core.config import Settings, get_settings

SettingsDep = Annotated[Settings, Depends(get_settings)]
# scope="function" commits before the response is sent, so a failed commit returns 500.
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session, scope="function")]


# TODO: replace with the tenant id from a verified JWT.
async def get_current_tenant_id(settings: SettingsDep) -> uuid.UUID:
    """Return the tenant of the caller. For now this is the fixed DEV_TENANT_ID."""
    return uuid.UUID(settings.dev_tenant_id)


def get_minio_client(settings: SettingsDep) -> Minio:
    return create_storage_client(settings)


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
) -> UserService:
    return UserService(user_repository=user_repository)


def get_chunk_service(
    doc_repository: Annotated[
        PostgresDocumentRepository, Depends(get_document_repository)
    ],
    chunk_repository: Annotated[PostgresChunkRepository, Depends(get_chunk_repository)],
) -> ChunkService:
    return ChunkService(
        doc_repository=doc_repository, chunk_repository=chunk_repository
    )
