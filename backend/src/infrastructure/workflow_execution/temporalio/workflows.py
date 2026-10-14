# src/infrastructure/workflow_execution/temporalio/workflows.py

import uuid
from datetime import timedelta

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
from src.libs.exceptions.exceptions import NotFoundException

with workflow.unsafe.imports_passed_through():
    from src.infrastructure.workflow_execution.temporalio.activities import (
        IngestFileActivities,
    )

""" Workflows are used to configure and organise the execution activities."""


@workflow.defn
class DocumentIngestionWorkflow:
    @workflow.run
    async def run(self, payload_dict: dict) -> str:
        """The main entry point for the workflow"""
        payload = IngestionPayload.model_validate(payload_dict)
        workflow_info = workflow.info()
        workflow.logger.info(
            "Starting durable ingestion workflow for document %s", payload.document_id
        )

        # Create new DB entry for document
        create_doc = CreateDocumentPayload(
            document_id=payload.document_id,
            tenant_id=payload.tenant_id,
            filename=payload.filename,
            document_type=payload.document_type,
            status="UPLOADED",
            bucket_name=payload.bucket_name,
            storage_type="MINIO",
            mime_type=payload.mime_type,
            storage_key=payload.object_key,
        )
        await workflow.execute_activity(
            IngestFileActivities.create_document_activity,
            args=[create_doc],
            schedule_to_close_timeout=timedelta(seconds=30),
        )

        # Create Ingestion Job record in DB
        job_id = str(uuid.uuid4())
        create_ingestion_job = CreateIngestionJobPayload(
            job_id=job_id,
            document_id=payload.document_id,
            workflow_id=workflow_info.workflow_id,
            workflow_run_id=workflow_info.run_id,
            current_stage="INITIALISING",
            status="PENDING",
        )
        await workflow.execute_activity(
            IngestFileActivities.create_ingestion_job_activity,
            args=[create_ingestion_job],
            schedule_to_close_timeout=timedelta(seconds=30),
        )

        # Execute Ingestion Job
        try:
            process_doc = ProcessDocumentPayload(
                document_id=payload.document_id,
                filename=payload.filename,
                bucket=payload.bucket_name,
                object_key=payload.object_key,
                etag=payload.etag,
                size_bytes=payload.size_bytes,
                mime_type=payload.mime_type,
            )
            await workflow.execute_activity(
                IngestFileActivities.process_document_activity,
                args=[process_doc],  # Pass validated data to activity
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(minutes=1),
                    maximum_attempts=5,
                    backoff_coefficient=2.0,
                ),
                schedule_to_close_timeout=timedelta(minutes=30),
                start_to_close_timeout=timedelta(minutes=15),
                heartbeat_timeout=timedelta(seconds=30),
            )
        except ActivityError as exc:
            workflow.logger.error(
                "Processing of document %s failed: %s",
                payload.document_id,
                exc.cause,
            )
            try:
                # Update DB entry for document
                updated_doc = UpdateDocumentPayload(
                    document_id=payload.document_id,
                    tenant_id=payload.tenant_id,
                    size_bytes=payload.size_bytes,
                    status="FAILED",
                    bucket_name=payload.bucket_name,
                )
                await workflow.execute_activity(
                    IngestFileActivities.update_document_activity,
                    args=[updated_doc],
                    schedule_to_close_timeout=timedelta(seconds=30),
                )

                # Update DB job entry for document
                updated_job = UpdateIngestionJobPayload(
                    job_id=job_id,
                    document_id=payload.document_id,
                    status="FAILED",
                    error_message=str(exc.cause),
                )
                await workflow.execute_activity(
                    IngestFileActivities.update_ingestion_job_activity,
                    args=[updated_job],
                    schedule_to_close_timeout=timedelta(seconds=30),
                )
            except NotFoundException as comp_exc:
                # Only raise the original exception cause
                workflow.logger.error(
                    "Compensation for document %s and job %s failed: %s",
                    payload.document_id,
                    job_id,
                    comp_exc,
                )

            raise ApplicationError(f"Workflow failed: {exc.cause}") from exc

        # Update DB entry for document
        updated_doc = UpdateDocumentPayload(
            document_id=payload.document_id,
            tenant_id=payload.tenant_id,
            size_bytes=payload.size_bytes,
            status="PROCESSED",
            bucket_name=payload.bucket_name,
        )
        await workflow.execute_activity(
            IngestFileActivities.update_document_activity,
            args=[updated_doc],
            schedule_to_close_timeout=timedelta(seconds=30),
        )

        # Update DB job status
        updated_job = UpdateIngestionJobPayload(
            job_id=job_id,
            document_id=payload.document_id,
            current_stage="COMPLETED",
            status="COMPLETED",
        )
        await workflow.execute_activity(
            IngestFileActivities.update_ingestion_job_activity,
            args=[updated_job],
            schedule_to_close_timeout=timedelta(seconds=30),
        )

        return f"Ingestion completed for document id {payload.document_id} with job id {job_id}"