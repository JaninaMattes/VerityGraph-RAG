import base64
import uuid
from typing import Annotated

from fastapi import Depends
from minio import Minio
from minio.sse import SseCustomerKey
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
from src.infrastructure.storage.minio.storage import MinioStorage
from src.shared.core.config import Settings, get_settings
from src.shared.core.logger import get_logger

logger = get_logger("api.dependencies")

# Reuse settings dependency across sub-providers
SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


# Provider wrapping the global client instance for FastAPI dependency integration
def get_minio_client(settings: SettingsDep) -> Minio:
    return Minio(
        endpoint=settings.minio_url,
        access_key=settings.minio_root_user.get_secret_value(),
        secret_key=settings.minio_root_password.get_secret_value(),
        region=settings.minio_region,
        secure=settings.minio_secure,
    )


# Reuse dependency across sub-providers
MinioClientDep = Annotated[Minio, Depends(get_minio_client)]

# Dependency provider testing
DEV_TENANT_ID = uuid.UUID("15a97078-162a-44f2-b950-d0d90d684fca")


async def get_current_tenant_id() -> uuid.UUID:
    """
    MVP Dependency: Returns a hardcoded tenant ID.
    TODO: decode the JWT and extract the tenant_id from there.
    """
    return DEV_TENANT_ID

# Dependency provider factories
def get_tenant_repository(session: DbSessionDep) -> PostgresTenantRepository:
    return PostgresTenantRepository(session=session)


def get_user_repository(session: DbSessionDep) -> PostgresUserRepository:
    return PostgresUserRepository(session=session)


def get_document_repository(session: DbSessionDep) -> PostgresDocumentRepository:
    return PostgresDocumentRepository(session=session)

def get_job_repository(session: DbSessionDep) -> PostgresIngestionJobRepository:
    return PostgresIngestionJobRepository(session=session)

def get_minio_provider(settings: SettingsDep, client: MinioClientDep) -> MinioStorage:
    storage = MinioStorage(
        client=client,
        bucket_name=settings.minio_default_bucket,
        sse_key=SseCustomerKey(
            key=base64.b64decode(settings.minio_sse_customer_key.get_secret_value())
        ),  # string to byte code
    )
    return storage


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