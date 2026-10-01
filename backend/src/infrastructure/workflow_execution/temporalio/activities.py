import asyncio
from typing import Any

from temporalio import activity
from temporalio.exceptions import (
    ApplicationError,
)

from src.domain.documents.repository import DocumentRepository
from src.infrastructure.storage.provider import StorageProvider
from src.shared.enums.document import DocumentStatus, DocumentType
from src.shared.enums.storage import StorageType


@activity.defn
async def say_hello(name: str) -> str:
    return f"Hello, {name}!"

class IngestFileActivities:
    def __init__(
        self,
        doc_repository: DocumentRepository,
        storage: StorageProvider,
    ) -> None:
        self.doc_repository = doc_repository
        self.storage = storage

    @activity.defn
    async def update_document_activity(
        self,
        document_id: str,
        size_bytes: int,
        document_type: DocumentType,
        status: DocumentStatus,
        bucket_name: str,
        storage_type: StorageType,
    ) -> None:
        activity.logger.info("Updating document %s to status %s.", document_id, status)
        info = activity.info()
        idempotency_key = f"{info.workflow_run_id}-{info.activity_id}"

        try:
            # SOTA: Pass the idempotency_key to your repository to prevent
            # duplicate writes if this activity is retried after a crash.
            # await self.doc_repository.update_status(
            #     document_id, status, idempotency_key=idempotency_key
            # )
            await asyncio.sleep(0.1)  # Simulate DB call
        except Exception as exc:
            raise ApplicationError(
                f"Failed to update document with id {document_id}.",
                non_retryable=False,
                type="DocumentUpdateFailure",
            ) from exc

    @activity.defn
    async def create_ingestion_job_activity(self, document_id: str) -> str:
        activity.logger.info("Creating new ingestion job for document %s.", document_id)
        info = activity.info()
        idempotency_key = f"{info.workflow_run_id}-{info.activity_id}"

        try:
            # job = await self.doc_repository.create_ingestion_job(document_id, idempotency_key)
            # return str(job.id)
            await asyncio.sleep(0.1)
            return "mock-job-id-123"
        except Exception as exc:
            raise ApplicationError(
                f"Failed to create ingestion job for document {document_id}.",
                non_retryable=False,
                type="DBFailure",
            ) from exc

    @activity.defn
    async def process_document_activity(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        # Ensure Idempotency
        info = activity.info()
        idempotency_key = f"{info.workflow_run_id}-{info.activity_id}"

        document_id = payload["document_id"]
        bucket = payload["bucket"]
        activity.logger.info(
            "Processing document %s from bucket %s.", document_id, bucket
        )

        try:
            # 1. Download from MinIO (StorageProvider should handle retries/timeouts internally)
            # file_bytes = await self.storage.download_file(bucket, document_id)
            await asyncio.sleep(1)  # Simulate download

            # 2. Heavy AI/ML work (chunking, embedding)
            # IMPORTANT: Use heartbeats for long-running activities to prevent timeouts
            # and allow resumption from the last successful step if the worker crashes.
            total_chunks = 5
            for i in range(total_chunks):
                activity.logger.info(
                    f"Processing chunk {i + 1}/{total_chunks} for {document_id}"
                )
                await asyncio.sleep(1)  # Simulate chunk processing

                # Heartbeat allows Temporal to know the activity is still alive
                # Can be used to resume if the activity is retried
                activity.heartbeat(f"Processed {i + 1}/{total_chunks} chunks")

            # 3. Return results to the Workflow (do NOT save final state to DB here;
            # let the Workflow call update_document_activity to ensure it only happens
            # after the workflow successfully completes, guaranteeing consistency).
            return {
                "document_id": document_id,
                "chunks_processed": total_chunks,
                "status": "SUCCESS",
            }

        except Exception as exc:
            # Make file-not-found errors non-retryable to avoid infinite loops
            is_non_retryable = "FileNotFound" in str(exc) or "NoSuchKey" in str(exc)
            raise ApplicationError(
                f"Failed to process document with id {document_id}: {exc}",
                non_retryable=is_non_retryable,
            ) from exc

    @activity.defn
    async def update_ingestion_job_activity(self, job_id: str, status: str) -> None:
        activity.logger.info("Updating ingestion job %s status to %s.", job_id, status)
        info = activity.info()
        idempotency_key = f"{info.workflow_run_id}-{info.activity_id}"

        try:
            # await self.doc_repository.update_job_status(job_id, status, idempotency_key)
            await asyncio.sleep(0.1)
        except Exception as exc:
            raise ApplicationError(
                f"Failed to update ingestion job with id {job_id}.",
                non_retryable=False,
                type="IngestionJobUpdateFailure",
            ) from exc