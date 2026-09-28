from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activity, passing it through the sandbox without reloading the module
with workflow.unsafe.imports_passed_through():
    from src.infrastructure.workflow_execution.temporalio.activities import (
        create_ingestion_job_activity,
        process_document_activity,
        say_hello,
        update_document_activity,
        update_ingestion_job_activity,
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
        workflow.logger.info(
            "Starting durable ingestion orchestration for %s", document_id
        )

        # 1. Update DB status
        await workflow.execute_activity(
            update_document_activity,
            args=[document_id, "UPLOADED"],
            schedule_to_close_timeout=timedelta(seconds=30),
        )

        # 2. Create Ingestion Job record in DB
        job_id = await workflow.execute_activity(
            create_ingestion_job_activity,
            args=[document_id],
            schedule_to_close_timeout=timedelta(seconds=30),
        )

        # 3. Execute Imgestion Job (MinIO download, chunking, embedding, compression)
        await workflow.execute_activity(
            process_document_activity,
            args=[payload],
            retry_policy=RetryPolicy(
                initial_interval=timedelta(minutes=1),
                maximum_attempts=5,
                backoff_coefficient=2.0,
                maximum_interval=timedelta(minutes=5),
            ),
            schedule_to_close_timeout=timedelta(minutes=30),
        )

        # 4. Update DB document status to COMPLETED
        await workflow.execute_activity(
            update_document_activity,
            args=[document_id, "PROCESSED"],
            schedule_to_close_timeout=timedelta(seconds=30),
        )

        # 4. Update DB job status to COMPLETED
        await workflow.execute_activity(
            update_ingestion_job_activity,
            args=[job_id, "PROCESSED"],
            schedule_to_close_timeout=timedelta(seconds=30),
        )

        return f"Ingestion completed for document id {document_id} with job id {job_id}"