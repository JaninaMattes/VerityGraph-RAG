# src/infrastructure/workflow_execution/temporalio/activities.py

import asyncio
import os
import tempfile
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker
from temporalio import activity
from temporalio.exceptions import ApplicationError, CancelledError

from src.domain.documents.dataclasses import StorageKey
from src.domain.documents.entities import DocumentEntity
from src.domain.ingestions.entities import IngestionJobEntity
from src.infrastructure.database.postgres.repositories.document import (
    PostgresDocumentRepository,
)
from src.infrastructure.database.postgres.repositories.ingestionjobs import (
    PostgresIngestionJobRepository,
)
from src.infrastructure.storage.provider import StorageProvider
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
    DocumentNotFoundException,
    IngestionJobNotFoundException,
)
from src.pipelines.ingestion.pipeline import IngestionPipeline


class IngestFileActivities:
    def __init__(
        self,
        session_factory: async_sessionmaker,
        storage: StorageProvider,
        ingestion_pipeline: IngestionPipeline,
    ) -> None:
        self._session_factory = session_factory
        self._storage = storage

    @activity.defn(name="create_document_activity")
    async def create_document_activity(self, payload: CreateDocumentPayload) -> None:
        info = activity.info()
        idempotency_key = f"{info.workflow_run_id}-{info.activity_id}"
        activity.logger.info(
            "Creating new document with id %s and status %s.",
            payload.document_id,
            payload.status,
        )

        # Explicit Transaction Management with guaranteed rollback
        async with self._session_factory() as session:
            try:
                try:
                    doc_type = DocumentType[payload.document_type.upper()]
                    doc_status = DocumentStatus[payload.status.upper()]
                    storage_type = StorageType[payload.storage_type.upper()]
                except KeyError as exc:
                    # Raises native KeyError. Data error hence mark as non-retryable.
                    raise ApplicationError(
                        f"Invalid payload value: {exc}. Expected a valid enum string.",
                        non_retryable=True,
                        type="DataValidationFailure",
                    ) from exc

                doc_repository = PostgresDocumentRepository(session)

                # Build database entity
                now = datetime.now(UTC)
                doc_entity = DocumentEntity(
                    document_id=UUID(payload.document_id),
                    tenant_id=UUID(payload.tenant_id),
                    filename=payload.filename,
                    mime_type=payload.mime_type,
                    document_type=doc_type,
                    bucket_name=payload.bucket_name,
                    storage_key=StorageKey(value=payload.storage_key),
                    storage_type=storage_type,
                    status=doc_status,
                    created_at=now,
                    updated_at=now,
                )
                await doc_repository.create(doc_entity, idempotency_key=idempotency_key)
                await session.commit()

            except ApplicationError:
                raise
            except Exception as exc:
                # Database error will be handled by temporal
                activity.logger.exception(
                    "Unexpected system failure creating document %s.",
                    payload.document_id,
                )
                raise ApplicationError(
                    f"Failed to create document {payload.document_id} in database.",
                    non_retryable=False,
                    type="DatabaseFailure",
                ) from exc

    @activity.defn(name="update_document_activity")
    async def update_document_activity(self, payload: UpdateDocumentPayload) -> None:
        info = activity.info()
        idempotency_key = f"{info.workflow_run_id}-{info.activity_id}"

        activity.logger.info(
            "Updating document %s to status %s.", payload.document_id, payload.status
        )

        # Explicit Transaction Management with guaranteed rollback
        async with self._session_factory() as session:
            try:
                doc_repository = PostgresDocumentRepository(session)
                doc_uuid = UUID(payload.document_id)
                tenant_uuid = UUID(payload.tenant_id)
                db_document = await doc_repository.get_one(doc_uuid, tenant_uuid)

                if db_document is None:
                    activity.logger.exception(
                        "The document %s couldn't be found in the database.", doc_uuid
                    )
                    raise DocumentNotFoundException(doc_uuid)

                db_document.size_bytes = payload.size_bytes
                db_document.bucket_name = payload.bucket_name

                if payload.status == "UPLOADED":
                    db_document.mark_uploaded()
                elif payload.status == "PROCESSED":
                    db_document.mark_processed()
                elif payload.status == "FAILED":
                    db_document.mark_failed()

                await doc_repository.update(
                    db_document, idempotency_key=idempotency_key
                )
                await session.commit()
            except DocumentNotFoundException as exc:
                # Business rule violation makes it non-retryable
                raise ApplicationError(
                    str(exc), non_retryable=True, type="NotFound"
                ) from exc
            except Exception as exc:
                # Temporal's retry policies handles transient DB errors
                raise ApplicationError(
                    f"Failed to update document {payload.document_id}",
                    non_retryable=False,
                    type="DatabaseFailure",
                ) from exc

    @activity.defn(name="create_ingestion_job_activity")
    async def create_ingestion_job_activity(
        self, payload: CreateIngestionJobPayload
    ) -> None:
        activity.logger.info(
            "Creating new ingestion job %s for document %s.",
            payload.job_id,
            payload.document_id,
        )
        info = activity.info()
        idempotency_key = f"{info.workflow_run_id}-{info.activity_id}"

        async with self._session_factory() as session:
            job_repository = PostgresIngestionJobRepository(session)
            try:
                try:
                    # Map primitives to Enums
                    current_job_stage = IngestionStage[payload.current_stage.upper()]
                    job_status = ProcessingStatus[payload.status.upper()]
                except KeyError as exc:
                    # Raises native KeyError. Data error hence mark as non-retryable.
                    raise ApplicationError(
                        f"Invalid payload value: {exc}. Expected a valid enum string.",
                        non_retryable=True,
                        type="DataValidationFailure",
                    ) from exc

                # Pass the idempotency_key to repository to prevent
                # duplicate writes if this activity is retried after a crash.
                now = datetime.now(UTC)
                db_job = IngestionJobEntity(
                    job_id=UUID(payload.job_id),
                    document_id=UUID(payload.document_id),
                    workflow_id=payload.workflow_id,
                    workflow_run_id=payload.workflow_run_id,
                    current_stage=current_job_stage,
                    status=job_status,
                    created_at=now,
                    updated_at=now,
                )
                await job_repository.create(db_job, idempotency_key=idempotency_key)
                await session.commit()

            except Exception as exc:
                raise ApplicationError(
                    f"Failed to create ingestion job for document with id {payload.document_id}.",
                    non_retryable=False,
                    type="DatabaseFailure",
                ) from exc

    @activity.defn(name="update_ingestion_job_activity")
    async def update_ingestion_job_activity(
        self, payload: UpdateIngestionJobPayload
    ) -> None:
        activity.logger.info(
            "Updating ingestion job %s status to %s.", payload.job_id, payload.status
        )
        info = activity.info()
        idempotency_key = f"{info.workflow_run_id}-{info.activity_id}"

        async with self._session_factory() as session:
            job_repository = PostgresIngestionJobRepository(session)
            try:
                job_uuid = UUID(payload.job_id)
                document_uuid = UUID(payload.document_id)
                db_job = await job_repository.get_one(
                    job_uuid,
                    document_uuid,
                )

                if db_job is None:
                    activity.logger.exception(
                        "The ingestion job %s couldn't be found in the database.",
                        job_uuid,
                    )
                    raise IngestionJobNotFoundException(job_uuid)

                if payload.status == "COMPLETED":
                    db_job.mark_completed()
                elif payload.status == "FAILED":
                    db_job.mark_failed(error=payload.error_message or "Unknown error")
                else:
                    try:
                        db_job.status = ProcessingStatus[payload.status.upper()]
                        db_job.updated_at = datetime.now(UTC)
                    except KeyError as exc:
                        # Raises native KeyError. Data error hence mark as non-retryable.
                        raise ApplicationError(
                            f"Invalid payload value: {exc}. Expected a valid enum string.",
                            non_retryable=True,
                            type="DataValidationFailure",
                        ) from exc

                # Pass the idempotency_key to the repository to prevent
                # duplicate writes if this activity is retried after a crash.
                await job_repository.update(db_job, idempotency_key=idempotency_key)
                await session.commit()
            except Exception as exc:
                activity.logger.exception(
                    "Failed to update ingestion job %s.",
                    payload.job_id,
                )
                raise ApplicationError(
                    f"Failed to update ingestion job status to {payload.status} for job with id {payload.job_id}.",
                    non_retryable=False,
                    type="DatabaseFailure",
                ) from exc

    @activity.defn
    async def process_document_activity(
        self, payload: ProcessDocumentPayload
    ) -> ProcessDocumentResult:
        info = activity.info()
        activity.logger.info(
            "Processing document %s from bucket %s.",
            payload.document_id,
            payload.bucket,
        )

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Download file to local temp file directly
                local_file_path = os.path.join(temp_dir, payload.filename)
                await asyncio.to_thread(
                    self._storage.download_object,
                    payload.bucket,
                    payload.object_key,
                    local_file_path,  # temporary local file path
                )
                total_chunks = 1000  # TODO: Update the process
                return ProcessDocumentResult(
                    document_id=payload.document_id,
                    chunks_processed=total_chunks,
                    status=DocumentStatus.PROCESSED.value,
                )
        except CancelledError:  # Temporal handles the cancellation propagation
            activity.logger.warning(
                "The processing of document %s was cancelled.",
                payload.document_id,
            )
            raise
        except Exception as exc:
            is_non_retryable = isinstance(exc, FileNotFoundError) or exc in (
                "NoSuchKey",
                "AccessDenied",
                "InvalidAccessKeyId",
            )
            activity.logger.exception(
                "The processing of document %s failed. The retry status is set to: %s",
                payload.document_id,
                is_non_retryable,
            )
            raise ApplicationError(
                f"Failed to process document {payload.document_id}: {exc}",
                non_retryable=is_non_retryable,
                type="ProcessingFailure",
            ) from exc
