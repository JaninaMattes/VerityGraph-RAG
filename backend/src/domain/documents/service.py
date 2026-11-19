"""Document use cases: presigned upload and download URLs."""

import asyncio
import uuid
from datetime import timedelta

from src.domain.documents.dataclasses import PresignedUrl, StorageKey
from src.domain.documents.repository import DocumentRepository
from src.domain.documents.storage import StorageProvider
from src.libs.core.logger import get_logger
from src.libs.exceptions.exceptions import BucketNotFoundException

logger = get_logger(__name__)

UPLOAD_URL_TTL = timedelta(minutes=15)
DOWNLOAD_URL_TTL = timedelta(minutes=5)


class DocumentService:
    """Issues presigned URLs so that file bytes never pass through the API.

    Storage and database errors propagate unchanged to the caller.
    """

    def __init__(
        self, storage: StorageProvider, doc_repository: DocumentRepository
    ) -> None:
        self.doc_repository = doc_repository
        self.storage = storage

    async def create_upload_url(
        self, tenant_id: uuid.UUID, filename: str, namespace: str = "files"
    ) -> PresignedUrl:
        """Return a presigned PUT URL for a new document of the tenant.

        The tenant id, filename and document type are signed into the URL as object
        metadata; the ingestion worker reads them from the upload event. If the bucket
        is missing, it is created once and signing is retried.
        """
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

        def sign() -> str:
            return self.storage.create_presigned_url(
                storage_key=storage_key,
                expires_at=UPLOAD_URL_TTL,
                method="PUT",
                user_metadata=user_metadata,
            )

        try:
            url = await asyncio.to_thread(sign)
        except BucketNotFoundException:
            logger.warning(
                "Bucket is missing. Creating it and retrying the upload URL."
            )
            await asyncio.to_thread(self.storage.create_bucket)
            url = await asyncio.to_thread(sign)

        return PresignedUrl(
            document_id=document_id,
            url=url,
            expires_at=UPLOAD_URL_TTL,
            required_headers={
                "x-amz-meta-tenant-id": str(tenant_id),
                "x-amz-meta-filename": filename,
                "x-amz-meta-document-type": document_type,
            },
        )

    async def get_download_url(
        self, document_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> PresignedUrl:
        """Return a presigned GET URL for a document of the tenant.

        Raise DocumentNotFoundException if the tenant has no such document.
        """
        document = await self.doc_repository.get_one(document_id, tenant_id)
        url = await asyncio.to_thread(
            self.storage.create_presigned_url,
            storage_key=document.storage_key,
            expires_at=DOWNLOAD_URL_TTL,
            method="GET",
        )
        document_type = (
            document.document_type.value if document.document_type else "unknown"
        )
        return PresignedUrl(
            document_id=document_id,
            url=url,
            expires_at=DOWNLOAD_URL_TTL,
            required_headers={
                "x-amz-meta-tenant-id": str(document.tenant_id),
                "x-amz-meta-filename": document.filename,
                "x-amz-meta-document-type": document_type,
            },
        )
