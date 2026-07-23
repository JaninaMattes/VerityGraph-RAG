from src.domain.documents.entities import DocumentEntity
from src.domain.documents.dataclasses import DocumentChecksum, StorageKey
from src.infrastructure.database.postgres.models.document import Document


class DocumentMapper:
    @staticmethod
    def to_model(entity: DocumentEntity) -> Document:
        return Document(
            document_id=entity.document_id,
            tenant_id=entity.tenant_id,
            filename=entity.filename,
            mime_type=entity.mime_type,
            document_type=entity.document_type,
            language=entity.language,
            bucket_name=entity.bucket_name,
            storage_key=entity.storage_key.value,  # string
            storage_provider=entity.storage_provider,
            version_id=entity.version_id,
            etag=entity.etag,
            checksum=entity.checksum.value,  # string
            size_bytes=entity.size_bytes,
            status=entity.status,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
            deleted_by=entity.deleted_by,
            # DB handles created_at/updated_at on creation
        )

    @staticmethod
    def to_entity(model: Document) -> DocumentEntity:
        return DocumentEntity(
            document_id=model.document_id,
            tenant_id=model.tenant_id,
            filename=model.filename,
            mime_type=model.mime_type,
            document_type=model.document_type,
            language=model.language,
            bucket_name=model.bucket_name,
            storage_key=StorageKey(model.storage_key),  # storage key
            storage_provider=model.storage_provider,
            version_id=model.version_id,
            etag=model.etag,
            checksum=DocumentChecksum.from_hex(model.checksum),
            size_bytes=model.size_bytes,
            status=model.status,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
            deleted_by=model.deleted_by,
        )
