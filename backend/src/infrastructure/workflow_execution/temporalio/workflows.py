from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.infrastructure.workflow_execution.temporalio.activities import (
        IngestFileActivities,
        say_hello,  # Additional standalone function
    )

""" Workflows are used to onfigure and organise the execution activities."""


@workflow.defn
class SayHello:
    @workflow.run
    async def run(self, name: str) -> str:
        return await workflow.execute_activity(
            say_hello, name, schedule_to_close_timeout=timedelta(seconds=10)
        )


@workflow.defn
class DocumentIngestionWorkflow:
    @workflow.run
    async def run(self, payload: dict[str, Any]) -> str:
        document_id = payload["document_id"]
        bucket_name = payload.get("bucket", "default-bucket")

        workflow.logger.info(
            "Starting durable ingestion orchestration for %s", document_id
        )

        # Helper to ensure enums are serialized as strings
        doc_type_val = payload.get("document_type", "UNKNOWN")
        if hasattr(doc_type_val, "value"):
            doc_type_val = doc_type_val.value

        # 1. Update DB status to UPLOADED
        await workflow.execute_activity(
            IngestFileActivities.update_document_activity,
            args=[
                document_id,
                payload.get("size_bytes", 0),
                doc_type_val,
                "UPLOADED",
                bucket_name,
            ],
            schedule_to_close_timeout=timedelta(seconds=30),
        )

        # 2. Create Ingestion Job record in DB
        job_id = await workflow.execute_activity(
            IngestFileActivities.create_ingestion_job_activity,
            args=[document_id],
            schedule_to_close_timeout=timedelta(seconds=30),
        )

        # 3. Execute Ingestion Job
        processing_result = await workflow.execute_activity(
            IngestFileActivities.process_document_activity,
            args=[payload],
            retry_policy=RetryPolicy(
                initial_interval=timedelta(minutes=1),
                maximum_attempts=5,
                backoff_coefficient=2.0,
                maximum_interval=timedelta(minutes=5),
            ),
            schedule_to_close_timeout=timedelta(minutes=30),
            # CRITICAL SOTA: Must be set when activity calls activity.heartbeat()
            heartbeat_timeout=timedelta(seconds=15),
        )

        # 4. Update DB document status to PROCESSED
        await workflow.execute_activity(
            IngestFileActivities.update_document_activity,
            args=[
                document_id,
                payload.get("size_bytes", 0),
                doc_type_val,
                "PROCESSED",
                bucket_name,
            ],
            schedule_to_close_timeout=timedelta(seconds=30),
        )

        # 5. Update DB job status to PROCESSED
        await workflow.execute_activity(
            IngestFileActivities.update_ingestion_job_activity,
            args=[job_id, "PROCESSED"],
            schedule_to_close_timeout=timedelta(seconds=30),
        )

        return f"Ingestion completed for document id {document_id} with job id {job_id}"