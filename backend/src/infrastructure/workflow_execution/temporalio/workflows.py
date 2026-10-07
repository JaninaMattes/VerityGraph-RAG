# src/infrastructure/workflow_execution/temporalio/workflows.py

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

from src.infrastructure.workflow_execution.temporalio.models import IngestionPayload

with workflow.unsafe.imports_passed_through():
    from src.infrastructure.workflow_execution.temporalio.activities import (
        IngestFileActivities,
    )

""" Workflows are used to onfigure and organise the execution activities."""


@workflow.defn
class DocumentIngestionWorkflow:
    @workflow.run
    async def run(self, payload_dict: dict) -> str:
        """The main entry point for the workflow"""
        payload = IngestionPayload.model_validate(payload_dict)
        workflow.logger.info(
            "Starting durable ingestion workflow for document %s", payload.document_id
        )

        # 1. Update DB status to UPLOADED
        await workflow.execute_activity(
            IngestFileActivities.update_document_activity,
            args=[
                payload.document_id,
                payload.size_bytes,
                payload.document_type,
                "UPLOADED",
                payload.bucket,
                "MINIO",
            ],
            schedule_to_close_timeout=timedelta(seconds=30),
        )

        # 2. Create Ingestion Job record in DB
        job_id = await workflow.execute_activity(
            IngestFileActivities.create_ingestion_job_activity,
            args=[payload.document_id],
            schedule_to_close_timeout=timedelta(seconds=30),
        )

        # 3. Execute Ingestion Job
        try:
            await workflow.execute_activity(
                IngestFileActivities.process_document_activity,
                args=[
                    payload.model_dump(mode="json")
                ],  # Pass validated data to activity
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(minutes=1),
                    maximum_attempts=5,
                    backoff_coefficient=2.0,
                ),
                start_to_close_timeout=timedelta(minutes=10),
                schedule_to_close_timeout=timedelta(minutes=30),
                heartbeat_timeout=timedelta(seconds=15),
            )
        except ActivityError as exc:
            workflow.logger.error(
                "Processing of document %s failed permanently: %s",
                payload.document_id,
                exc.cause,
            )
            await workflow.execute_activity(
                IngestFileActivities.update_document_activity,
                args=[
                    payload.document_id,
                    payload.size_bytes,
                    payload.document_type,
                    "FAILED",
                    payload.bucket,
                    "MINIO",
                ],
                schedule_to_close_timeout=timedelta(seconds=30),
            )
            raise ApplicationError(
                f"Workflow failed during processing: {exc.cause}"
            ) from exc

        # 4. Update DB document status to PROCESSED
        await workflow.execute_activity(
            IngestFileActivities.update_document_activity,
            args=[
                payload.document_id,
                payload.size_bytes,
                payload.document_type,
                "PROCESSED",
                payload.bucket,
                "MINIO",
            ],
            schedule_to_close_timeout=timedelta(seconds=30),
        )

        # 5. Update DB job status to PROCESSED
        await workflow.execute_activity(
            IngestFileActivities.update_ingestion_job_activity,
            args=[job_id, "PROCESSED"],
            schedule_to_close_timeout=timedelta(seconds=30),
        )

        return f"Ingestion completed for document id {payload.document_id} with job id {job_id}"