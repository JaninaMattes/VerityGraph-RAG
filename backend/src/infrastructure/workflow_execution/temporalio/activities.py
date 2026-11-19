"""Temporal activities of the document ingestion workflow.

Each database activity uses its own session and commits once at the end. Errors are
classified for Temporal's retry policy:
- invalid payload values (ValueError)   -> non-retryable 'DataValidationFailure';
- missing records (NotFoundException)   -> non-retryable 'NotFound';
- duplicate keys (ConflictException)    -> non-retryable 'Conflict';
- any other error (database, network)   -> retryable 'DatabaseFailure'.
"""

import asyncio
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path, PurePosixPath
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from temporalio import activity
from temporalio.exceptions import ApplicationError

from src.domain.chunks.chunker import DocumentChunker
from src.domain.chunks.entities import build_chunks
from src.domain.documents.dataclasses import StorageKey
from src.domain.documents.entities import DocumentEntity
from src.domain.documents.storage import StorageProvider
from src.domain.ingestions.entities import IngestionJobEntity
from src.infrastructure.database.postgres.repositories.chunk import (
    PostgresChunkRepository,
)
from src.infrastructure.database.postgres.repositories.document import (
    PostgresDocumentRepository,
)
from src.infrastructure.database.postgres.repositories.ingestionjobs import (
    PostgresIngestionJobRepository,
)
from src.infrastructure.workflow_execution.temporalio.models import (
    CreateDocumentPayload,
    CreateIngestionJobPayload,
    ProcessDocumentPayload,
    ProcessDocumentResult,
    UpdateDocumentPayload,
    UpdateIngestionJobPayload,
)
from src.libs.enums.document import DocumentStatus, DocumentType
from src.libs.enums.ingestionjob import IngestionStage, ProcessingStatus
from src.libs.enums.storage import StorageType
from src.libs.exceptions.exceptions import (
    ConflictException,
    DocumentParsingException,
    NotFoundException,
    StorageAccessDeniedException,
)

# Status name in the payload -> domain transition of the document.
DOCUMENT_TRANSITIONS: dict[str, Callable[[DocumentEntity], None]] = {
    "UPLOADED": DocumentEntity.mark_uploaded,
    "PROCESSED": DocumentEntity.mark_processed,
    "FAILED": DocumentEntity.mark_failed,
}

# Errors that a retry of process_document_activity cannot fix.
PERMANENT_PROCESSING_ERRORS = (
    FileNotFoundError,
    NotFoundException,
    StorageAccessDeniedException,
    DocumentParsingException,
)


def parse_enum[E: Enum](enum_cls: type[E], name: str) -> E:
    """Return the member of `enum_cls` named `name` (case-insensitive).

    Raise ValueError for an unknown name.
    """
    try:
        return enum_cls[name.upper()]
    except KeyError:
        raise ValueError(f"'{name}' is not a valid {enum_cls.__name__}.") from None


@contextmanager
def _activity_errors(action: str) -> Iterator[None]:
    """Translate errors raised while doing `action` to classified ApplicationErrors."""
    try:
        yield
    except ValueError as exc:
        raise ApplicationError(
            f"Invalid payload: {exc}", non_retryable=True, type="DataValidationFailure"
        ) from exc
    except NotFoundException as exc:
        raise ApplicationError(str(exc), non_retryable=True, type="NotFound") from exc
    except ConflictException as exc:
        raise ApplicationError(str(exc), non_retryable=True, type="Conflict") from exc
    except Exception as exc:
        activity.logger.exception("Failed to %s.", action)
        raise ApplicationError(f"Failed to {action}.", type="DatabaseFailure") from exc


class IngestFileActivities:
    """Activities with their dependencies. Register the bound methods on a Worker."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        storage: StorageProvider,
        chunker: DocumentChunker,
        *,
        max_file_bytes: int,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage
        self._chunker = chunker
        self._max_file_bytes = max_file_bytes

    @activity.defn(name="create_document_activity")
    async def create_document_activity(self, payload: CreateDocumentPayload) -> None:
        """Store the uploaded document. Safe to retry: an existing row is overwritten."""
        with _activity_errors(f"create document {payload.document_id}"):
            now = datetime.now(UTC)
            document = DocumentEntity(
                document_id=UUID(payload.document_id),
                tenant_id=UUID(payload.tenant_id),
                filename=payload.filename,
                mime_type=payload.mime_type,
                document_type=parse_enum(DocumentType, payload.document_type),
                bucket_name=payload.bucket_name,
                storage_key=StorageKey(value=payload.storage_key),
                storage_type=parse_enum(StorageType, payload.storage_type),
                status=parse_enum(DocumentStatus, payload.status),
                created_at=now,
                updated_at=now,
            )
            async with self._session_factory() as session:
                await PostgresDocumentRepository(session).create(document)
                await session.commit()

    @activity.defn(name="update_document_activity")
    async def update_document_activity(self, payload: UpdateDocumentPayload) -> None:
        """Move the document to UPLOADED, PROCESSED or FAILED and store size and bucket."""
        with _activity_errors(f"update document {payload.document_id}"):
            transition = DOCUMENT_TRANSITIONS.get(payload.status)
            if transition is None:
                raise ValueError(
                    f"'{payload.status}' is not a supported document status."
                )
            async with self._session_factory() as session:
                repository = PostgresDocumentRepository(session)
                document = await repository.get_one(
                    UUID(payload.document_id), UUID(payload.tenant_id)
                )
                document.size_bytes = payload.size_bytes
                document.bucket_name = payload.bucket_name
                transition(document)
                await repository.update(document)
                await session.commit()

    @activity.defn(name="create_ingestion_job_activity")
    async def create_ingestion_job_activity(
        self, payload: CreateIngestionJobPayload
    ) -> None:
        """Store a new ingestion job. Safe to retry: an existing row is overwritten."""
        with _activity_errors(f"create ingestion job {payload.job_id}"):
            now = datetime.now(UTC)
            job = IngestionJobEntity(
                job_id=UUID(payload.job_id),
                document_id=UUID(payload.document_id),
                workflow_id=payload.workflow_id,
                workflow_run_id=payload.workflow_run_id,
                current_stage=parse_enum(IngestionStage, payload.current_stage),
                status=parse_enum(ProcessingStatus, payload.status),
                created_at=now,
                updated_at=now,
            )
            async with self._session_factory() as session:
                await PostgresIngestionJobRepository(session).create(job)
                await session.commit()

    @activity.defn(name="update_ingestion_job_activity")
    async def update_ingestion_job_activity(
        self, payload: UpdateIngestionJobPayload
    ) -> None:
        """Move the job to a new status. FAILED stores the error message."""
        with _activity_errors(f"update ingestion job {payload.job_id}"):
            status = parse_enum(ProcessingStatus, payload.status)
            async with self._session_factory() as session:
                repository = PostgresIngestionJobRepository(session)
                job = await repository.get_one(
                    UUID(payload.job_id), UUID(payload.document_id)
                )
                if status is ProcessingStatus.COMPLETED:
                    job.mark_completed()
                elif status is ProcessingStatus.FAILED:
                    job.mark_failed(error=payload.error_message or "Unknown error")
                else:
                    job.status = status
                    if payload.current_stage:
                        job.current_stage = parse_enum(
                            IngestionStage, payload.current_stage
                        )
                    job.updated_at = datetime.now(UTC)
                await repository.update(job)
                await session.commit()

    @activity.defn(name="process_document_activity")
    async def process_document_activity(
        self, payload: ProcessDocumentPayload
    ) -> ProcessDocumentResult:
        """Download the document, chunk it and store the chunks in one transaction.

        The local file name comes from the server-generated object key, never from the
        client filename, so a name like '../../x' cannot escape the directory.
        The chunks replace earlier chunks of the document, so a retry is safe.
        A file larger than `max_file_bytes` (as the upload event reports) fails
        before the download. Missing objects, missing files, denied access, too
        large and unreadable files are non-retryable; database and network faults
        are retryable.
        """
        activity.logger.info("Processing document %s.", payload.document_id)
        document_id, tenant_id = UUID(payload.document_id), UUID(payload.tenant_id)
        try:
            if payload.size_bytes > self._max_file_bytes:
                raise DocumentParsingException(
                    f"The file has {payload.size_bytes} bytes; "
                    f"the limit is {self._max_file_bytes}."
                )
            with tempfile.TemporaryDirectory() as temp_dir:
                local_path = Path(temp_dir) / PurePosixPath(payload.object_key).name
                await asyncio.to_thread(
                    self._storage.download_object,
                    payload.bucket,
                    payload.object_key,
                    str(local_path),
                )
                drafts = await asyncio.to_thread(self._chunker.chunk, local_path)
            config = self._chunker.config
            chunks = build_chunks(
                drafts, document_id=document_id, tenant_id=tenant_id, config=config
            )
            async with self._session_factory() as session:
                await PostgresChunkRepository(session).replace_for_document(
                    document_id, tenant_id, config, chunks
                )
                await session.commit()
            activity.logger.info(
                "Stored %d chunks of document %s.", len(chunks), payload.document_id
            )
            return ProcessDocumentResult(
                document_id=payload.document_id,
                chunks_processed=len(chunks),
                status=DocumentStatus.PROCESSED.value,
            )
        except Exception as exc:
            permanent = isinstance(exc, PERMANENT_PROCESSING_ERRORS)
            activity.logger.exception(
                "Processing of document %s failed (permanent=%s).",
                payload.document_id,
                permanent,
            )
            raise ApplicationError(
                f"Failed to process document {payload.document_id}: {exc}",
                non_retryable=permanent,
                type="ProcessingFailure",
            ) from exc
