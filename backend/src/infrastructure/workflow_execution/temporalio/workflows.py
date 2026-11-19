"""The durable document ingestion workflow.

Workflow code must be deterministic: use workflow.uuid4() and workflow.now(), never
uuid.uuid4(), datetime.now() or random. All I/O happens in activities.
"""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

from src.infrastructure.workflow_execution.temporalio.models import (
    CreateDocumentPayload,
    CreateIngestionJobPayload,
    IngestionPayload,
    ProcessDocumentPayload,
    UpdateDocumentPayload,
    UpdateIngestionJobPayload,
)

with workflow.unsafe.imports_passed_through():
    from src.infrastructure.workflow_execution.temporalio.activities import (
        IngestFileActivities,
    )

DB_ACTIVITY_TIMEOUT = timedelta(seconds=30)


def processing_task_queue(task_queue: str) -> str:
    """Return the task queue of the parsing activity for a workflow's `task_queue`.

    Parsing is slow and memory-heavy, so its own queue lets a worker limit how many
    files it parses at once without blocking the short database activities.
    """
    return f"{task_queue}-processing"


PROCESSING_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(minutes=1), maximum_attempts=5, backoff_coefficient=2.0
)


@workflow.defn
class DocumentIngestionWorkflow:
    """Record an uploaded document, chunk it into Postgres, and record the outcome.

    On a processing failure the document and the job are marked FAILED and the
    workflow fails with the processing error. A failure of this clean-up is logged
    and does not hide the processing error.
    """

    @workflow.run
    async def run(self, payload_dict: dict[str, Any]) -> str:
        payload = IngestionPayload.model_validate(payload_dict)
        info = workflow.info()
        job_id = str(workflow.uuid4())  # deterministic across replays

        await self._db_activity(
            IngestFileActivities.create_document_activity,
            CreateDocumentPayload(
                document_id=payload.document_id,
                tenant_id=payload.tenant_id,
                filename=payload.filename,
                document_type=payload.document_type,
                status="UPLOADED",
                bucket_name=payload.bucket_name,
                storage_type="MINIO",
                mime_type=payload.mime_type,
                storage_key=payload.object_key,
            ),
        )
        await self._db_activity(
            IngestFileActivities.create_ingestion_job_activity,
            CreateIngestionJobPayload(
                job_id=job_id,
                document_id=payload.document_id,
                workflow_id=info.workflow_id,
                workflow_run_id=info.run_id,
            ),
        )

        await self._db_activity(
            IngestFileActivities.update_ingestion_job_activity,
            UpdateIngestionJobPayload(
                job_id=job_id,
                document_id=payload.document_id,
                status="RUNNING",
                current_stage="CHUNKING",
            ),
        )

        try:
            await workflow.execute_activity_method(
                IngestFileActivities.process_document_activity,
                ProcessDocumentPayload(
                    document_id=payload.document_id,
                    tenant_id=payload.tenant_id,
                    filename=payload.filename,
                    bucket=payload.bucket_name,
                    object_key=payload.object_key,
                    etag=payload.etag,
                    size_bytes=payload.size_bytes,
                    mime_type=payload.mime_type,
                ),
                task_queue=processing_task_queue(workflow.info().task_queue),
                retry_policy=PROCESSING_RETRY_POLICY,
                # No schedule-to-close deadline: in a backlog the activity waits in
                # its queue instead of failing; each attempt is still limited.
                start_to_close_timeout=timedelta(minutes=15),
            )
        except ActivityError as exc:
            workflow.logger.error(
                "Processing of %s failed: %s", payload.document_id, exc.cause
            )
            try:
                await self._record_outcome(payload, job_id, "FAILED", str(exc.cause))
            except ActivityError as cleanup_exc:
                workflow.logger.error(
                    "Clean-up for %s failed: %s", payload.document_id, cleanup_exc.cause
                )
            raise ApplicationError(f"Workflow failed: {exc.cause}") from exc

        await self._record_outcome(payload, job_id, "COMPLETED")
        return f"Ingestion completed for document id {payload.document_id} with job id {job_id}"

    async def _db_activity(self, activity_fn: Callable[..., Any], payload: Any) -> None:
        """Run a short database activity with the default retry policy."""
        await workflow.execute_activity_method(
            activity_fn, payload, schedule_to_close_timeout=DB_ACTIVITY_TIMEOUT
        )

    async def _record_outcome(
        self,
        payload: IngestionPayload,
        job_id: str,
        job_status: str,
        error_message: str | None = None,
    ) -> None:
        """Mark the document PROCESSED (or FAILED) and the job with `job_status`."""
        await self._db_activity(
            IngestFileActivities.update_document_activity,
            UpdateDocumentPayload(
                document_id=payload.document_id,
                tenant_id=payload.tenant_id,
                size_bytes=payload.size_bytes,
                status="FAILED" if job_status == "FAILED" else "PROCESSED",
                bucket_name=payload.bucket_name,
            ),
        )
        await self._db_activity(
            IngestFileActivities.update_ingestion_job_activity,
            UpdateIngestionJobPayload(
                job_id=job_id,
                document_id=payload.document_id,
                status=job_status,
                error_message=error_message,
            ),
        )
