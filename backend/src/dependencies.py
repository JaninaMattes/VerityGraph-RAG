import base64
from typing import Annotated
import uuid

from fastapi import Depends
from minio import Minio
from minio.sse import SseCustomerKey
from sqlalchemy.ext.asyncio import AsyncSession

from src.workflows.client import WorkflowClient
from src.infrastructure.storage.minio.storage import MinioStorage
from src.infrastructure.database.postgres.repositories.document import (
    PostgresDocumentRepository,
)
from src.infrastructure.database.postgres.session import get_db_session
from src.domain.documents.service import DocumentService
from src.domain.auth.dataclasses import Principal
from src.core.config import Settings, get_settings


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
        endpoint=settings.minio_url,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        region=settings.minio_region,
        secure=settings.minio_secure,
    )


def get_workflow_client() -> WorkflowClient:
    return WorkflowClient()


# Reuse dependency across sub-providers
MinioClientDep = Annotated[Minio, Depends(get_minio_client)]


# Dependency provider factories
def get_document_repository(session: DbSessionDep) -> PostgresDocumentRepository:
    return PostgresDocumentRepository(session=session)


def get_storage_provider(settings: SettingsDep, client: MinioClientDep) -> MinioStorage:
    storage = MinioStorage(
        client=client,
        bucket=settings.minio_bucket_name,
        sse_key=SseCustomerKey(
            key=base64.b64decode(settings.minio_sse_customer_key)
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
