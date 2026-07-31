import base64
import uuid
from typing import Annotated

from fastapi import Depends
from minio import Minio
from minio.sse import SseCustomerKey
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.domain.auth.dataclasses import Principal
from src.domain.documents.service import DocumentService
from src.domain.tenants.service import TenantService
from src.domain.users.service import UserService
from src.infrastructure.database.postgres.repositories.credentials import (
    PostgresCredentialsRepository,
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
from src.infrastructure.storage.minio.storage import MinioStorage
from src.workflows.client import WorkflowClient


# Dummy user authentication dependency
def get_current_user() -> Principal:
    return Principal(
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        email="dummy-email@mail.com",
    )


# Reuse settings dependency across sub-providers
SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


# Provider wrapping the global client instance for FastAPI dependency integration
def get_minio_client(settings: SettingsDep) -> Minio:
    return Minio(
        endpoint=settings.storage_url,
        access_key=settings.storage_access_key,
        secret_key=settings.storage_secret_key,
        region=settings.storage_region,
        secure=settings.storage_secure,
    )


def get_workflow_client() -> WorkflowClient:
    return WorkflowClient()


# Reuse dependency across sub-providers
MinioClientDep = Annotated[Minio, Depends(get_minio_client)]


# Dependency provider factories
def get_tenant_repository(session: DbSessionDep) -> PostgresTenantRepository:
    return PostgresTenantRepository(session=session)


def get_user_repository(session: DbSessionDep) -> PostgresUserRepository:
    return PostgresUserRepository(session=session)

def get_credentials_repository(session: DbSessionDep) -> PostgresCredentialsRepository:
    return PostgresCredentialsRepository(session=session)

def get_document_repository(session: DbSessionDep) -> PostgresDocumentRepository:
    return PostgresDocumentRepository(session=session)

def get_storage_provider(settings: SettingsDep, client: MinioClientDep) -> MinioStorage:
    storage = MinioStorage(
        client=client,
        bucket_name=settings.storage_default_buckets,
        sse_key=SseCustomerKey(
            key=base64.b64decode(settings.storage_sse_customer_key)
        ),  # string to byte code
    )
    storage.create_bucket()  # TODO: Move to CI/CD pipeline
    return storage


# Define dependencies for services
def get_document_service(
    repository: Annotated[PostgresDocumentRepository, Depends(get_document_repository)],
    storage: Annotated[MinioStorage, Depends(get_storage_provider)],
    workflow: Annotated[WorkflowClient, Depends(get_workflow_client)],
) -> DocumentService:
    return DocumentService(repository=repository, storage=storage, workflow=workflow)


def get_tenant_service(
    repository: Annotated[PostgresTenantRepository, Depends(get_tenant_repository)],
) -> TenantService:
    return TenantService(repository=repository)


def get_user_service(
    user_repository: Annotated[PostgresUserRepository, Depends(get_user_repository)],
    credentials_repository: Annotated[
        PostgresCredentialsRepository, Depends(get_credentials_repository)
    ],
) -> UserService:
    return UserService(
        user_repository=user_repository, credentials_repository=credentials_repository
    )