# src/api/dependencies.py

import uuid
from typing import Annotated

from fastapi import Depends
from minio import Minio
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.documents.service import DocumentService
from src.domain.tenants.service import TenantService
from src.domain.users.service import UserService
from src.infrastructure.database.postgres.repositories.document import (
    PostgresDocumentRepository,
)
from src.infrastructure.database.postgres.repositories.ingestionjobs import (
    PostgresIngestionJobRepository,
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
from src.libs.core.logger import get_logger

logger = get_logger("api.dependencies")


# Reuse settings dependency across sub-providers
SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]

# TODO: NEEDS TO BE REPLACED WITH A REAL AUTH PROVIDER
async def get_current_tenant_id(settings: SettingsDep) -> uuid.UUID:
    """
    MVP Dependency: Returns a hardcoded tenant ID.
    TODO: decode the JWT and extract the tenant_id from there.
    """
    return uuid.UUID(settings.dev_tenant_id)


# Provider wrapping the global client instance for FastAPI dependency integration
def get_minio_client(settings: SettingsDep) -> Minio:
    return create_storage_client(settings)


# Reuse dependency across sub-providers
MinioClientDep = Annotated[Minio, Depends(get_minio_client)]


def get_minio_provider(settings: SettingsDep, client: MinioClientDep) -> MinioStorage:
    return create_storage_service(client, settings)


# Dependency provider factories
def get_tenant_repository(session: DbSessionDep) -> PostgresTenantRepository:
    return PostgresTenantRepository(session=session)


def get_user_repository(session: DbSessionDep) -> PostgresUserRepository:
    return PostgresUserRepository(session=session)


def get_document_repository(session: DbSessionDep) -> PostgresDocumentRepository:
    return PostgresDocumentRepository(session=session)


def get_job_repository(session: DbSessionDep) -> PostgresIngestionJobRepository:
    return PostgresIngestionJobRepository(session=session)


# Define dependencies for services
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