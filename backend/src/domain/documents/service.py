# src/domain/documents/service.py

import asyncio
import uuid
from datetime import timedelta

from src.domain.documents.dataclasses import StorageKey
from src.domain.documents.repository import DocumentRepository
from src.infrastructure.storage.provider import StorageProvider
from src.libs.core.logger import get_logger
from src.libs.exceptions.exceptions import (
    BucketNotFoundException,
    DatabaseException,
    DocumentServiceException,
    NotFoundException,
    StorageException,
)
from src.libs.schemas.document import (
    PresignedURLResponse,
)

logger = get_logger("api.domain.doc.service")


class DocumentService:
    """The service layer defines the business logic that ineracts with the repository."""

    def __init__(
        self,
        storage: StorageProvider,
        doc_repository: DocumentRepository,
    ) -> None:
        self.doc_repository = doc_repository
        self.storage = storage

    async def create_upload_url(
        self,
        tenant_id: uuid.UUID,  # Injected from settings/dependency
        filename: str,
        namespace: str = "files",
    ) -> PresignedURLResponse:
        """Create presigned PUT URL to upload file to S3 bucket."""

        # Create storage key
        document_id = uuid.uuid4()
        storage_key = StorageKey.document(
            document_id=document_id,
            tenant_id=tenant_id,
            namespace=namespace,
            original_filename=filename,
        )
        document_type = (
            filename.rsplit(".", 1)[-1].upper() if "." in filename else "UNKNOWN"
        )
        user_metadata = {
            "tenant_id": str(tenant_id),
            "filename": filename,
            "document_type": document_type,
        }

        expires_at = timedelta(minutes=15)  # 15 mins expiration time

        async def _create_presigned_url() -> str:
            return await asyncio.to_thread(
                self.storage.create_presigned_url,
                storage_key=storage_key,
                expires_at=expires_at,
                method="PUT",
                user_metadata=user_metadata,
            )

        try:
            # Create presigned URL
            presigned_url = await _create_presigned_url()
        except BucketNotFoundException:
            logger.exception(
                "The specified bucket was not found. Trying to auto-create the missing bucket."
            )
            try:
                await asyncio.to_thread(
                    self.storage.create_bucket,
                )
            except StorageException as bucket_exc:
                logger.exception(
                    "Failed to auto-create bucket for tenant %s.", tenant_id
                )
                raise DocumentServiceException(
                    "Failed to initialize storage for file upload."
                ) from bucket_exc

            try:
                # Auto-retry creating presigned URL
                presigned_url = await _create_presigned_url()
            except Exception as retry_exc:
                logger.exception(
                    "Failed generating presigned URL for document %s after auto-creating missing bucket.",
                    document_id,
                )
                raise DocumentServiceException(
                    "Failed to initialize file upload."
                ) from retry_exc

        except StorageException:
            raise
        except Exception as exc:
            logger.exception(
                "System failure when generating upload signatures for document %s.",
                document_id,
            )
            raise DocumentServiceException(
                "Failed to initialize file upload.",
            ) from exc

        return PresignedURLResponse(
            document_id=document_id,
            url=presigned_url,
            expires_at=expires_at,
            required_headers={
                "x-amz-meta-tenant-id": str(tenant_id),
                "x-amz-meta-filename": filename,
                "x-amz-meta-document-type": document_type,
            },
        )

    async def get_download_url(
        self,
        document_id: uuid.UUID,
        tenant_id: uuid.UUID,  # Injected from settings/dependency
    ) -> PresignedURLResponse:
        """Create presigned GET URL to download file from S3 bucket."""
        try:
            # Check first if file is there
            db_document = await self.doc_repository.get_one(document_id, tenant_id)

            expires_at = timedelta(minutes=5)  # 5 mins expiration time
            presigned_url = await asyncio.to_thread(
                self.storage.create_presigned_url,
                storage_key=db_document.storage_key,
                expires_at=expires_at,
                method="GET",
            )
            return PresignedURLResponse(
                document_id=document_id,
                url=presigned_url,
                expires_at=expires_at,
                required_headers={
                    "x-amz-meta-tenant-id": str(db_document.tenant_id),
                    "x-amz-meta-filename": db_document.filename,
                    "x-amz-meta-document-type": db_document.document_type.value
                    if db_document.document_type
                    else "unknown",
                },
            )
        except DatabaseException:
            raise
        except StorageException:
            raise
        except NotFoundException:
            raise
        except Exception as exc:
            logger.exception(
                "Unexpected error occured when generating presigned GET URL for document %s.",
                document_id,
            )
            raise DocumentServiceException(
                "Failed to initialize file download.",
            ) from exc
