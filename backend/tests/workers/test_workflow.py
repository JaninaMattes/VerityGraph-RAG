"""Tests for the document ingestion workflow on a Temporal time-skipping test server."""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio
from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker

from src.infrastructure.workflow_execution.temporalio.models import (
    CreateDocumentPayload,
    CreateIngestionJobPayload,
    IngestionPayload,
    ProcessDocumentPayload,
    ProcessDocumentResult,
    UpdateDocumentPayload,
    UpdateIngestionJobPayload,
)
from src.infrastructure.workflow_execution.temporalio.workflows import (
    DocumentIngestionWorkflow,
)

pytestmark = pytest.mark.asyncio

TASK_QUEUE = "test-ingestion"
DOCUMENT_ID = str(uuid.uuid4())
TENANT_ID = str(uuid.uuid4())


class FakeActivities:
    """Activity doubles that record each call and fail on request."""

    def __init__(
        self, *, fail_processing: bool = False, fail_compensation: bool = False
    ):
        self.calls: list[tuple[str, Any]] = []
        self.fail_processing = fail_processing
        self.fail_compensation = fail_compensation

    def all(self) -> list[Any]:
        @activity.defn(name="create_document_activity")
        async def create_document(payload: CreateDocumentPayload) -> None:
            self.calls.append(("create_document", payload))

        @activity.defn(name="create_ingestion_job_activity")
        async def create_job(payload: CreateIngestionJobPayload) -> None:
            self.calls.append(("create_job", payload))

        @activity.defn(name="process_document_activity")
        async def process(payload: ProcessDocumentPayload) -> ProcessDocumentResult:
            self.calls.append(("process", payload))
            if self.fail_processing:
                raise ApplicationError("parser exploded", non_retryable=True)
            return ProcessDocumentResult(
                document_id=payload.document_id, chunks_processed=0, status="processed"
            )

        @activity.defn(name="update_document_activity")
        async def update_document(payload: UpdateDocumentPayload) -> None:
            self.calls.append(("update_document", payload))
            if self.fail_compensation:
                raise ApplicationError("database down", non_retryable=True)

        @activity.defn(name="update_ingestion_job_activity")
        async def update_job(payload: UpdateIngestionJobPayload) -> None:
            self.calls.append(("update_job", payload))

        return [create_document, create_job, process, update_document, update_job]

    def names(self) -> list[str]:
        return [name for name, _ in self.calls]

    def payload(self, name: str) -> Any:
        return next(payload for call, payload in self.calls if call == name)


def ingestion_payload() -> dict[str, Any]:
    return IngestionPayload(
        document_id=DOCUMENT_ID,
        tenant_id=TENANT_ID,
        filename="report.pdf",
        bucket_name="files",
        object_key=f"{TENANT_ID}/files/2026/01/{DOCUMENT_ID}.pdf",
        etag="abc",
        size_bytes=2048,
        mime_type="application/pdf",
        document_type="PDF",
    ).model_dump(mode="json")


@pytest_asyncio.fixture
async def env() -> AsyncGenerator[WorkflowEnvironment]:
    async with await WorkflowEnvironment.start_time_skipping(
        data_converter=pydantic_data_converter
    ) as environment:
        yield environment


async def run_workflow(env: WorkflowEnvironment, fakes: FakeActivities) -> Any:
    """Run the workflow to its end.

    A workflow task error (for example a sandbox violation) is retried forever by
    Temporal, so the run is bounded by a timeout to fail fast instead of hanging.
    """
    async with (
        Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[DocumentIngestionWorkflow],
            activities=fakes.all(),
        ),
        asyncio.timeout(30),
    ):
        return await env.client.execute_workflow(
            DocumentIngestionWorkflow.run,
            ingestion_payload(),
            id=f"ingestion-job-{DOCUMENT_ID}",
            task_queue=TASK_QUEUE,
        )


class TestSuccessfulIngestion:
    """A successful run records the document, processes it and marks both as done."""

    async def test_activities_run_in_order_with_expected_payloads(
        self, env: WorkflowEnvironment
    ):
        """
        GIVEN all activities succeed
        WHEN the workflow runs
        THEN it creates the document and the job, processes the document,
        AND marks the document PROCESSED and the job COMPLETED
        """
        fakes = FakeActivities()

        result = await run_workflow(env, fakes)

        assert fakes.names() == [
            "create_document",
            "create_job",
            "process",
            "update_document",
            "update_job",
        ]
        created = fakes.payload("create_document")
        assert created.status == "UPLOADED"
        assert created.storage_type == "MINIO"
        assert created.storage_key == ingestion_payload()["object_key"]
        assert fakes.payload("update_document").status == "PROCESSED"
        assert fakes.payload("update_job").status == "COMPLETED"
        assert DOCUMENT_ID in result

    async def test_job_id_is_stable_within_a_run(self, env: WorkflowEnvironment):
        """
        GIVEN all activities succeed
        WHEN the workflow runs
        THEN the job that is created is the job that is completed
        AND the job references the workflow run
        """
        fakes = FakeActivities()

        await run_workflow(env, fakes)

        created = fakes.payload("create_job")
        assert fakes.payload("update_job").job_id == created.job_id
        assert created.workflow_id == f"ingestion-job-{DOCUMENT_ID}"
        uuid.UUID(created.job_id)

    async def test_history_replays_deterministically(self, env: WorkflowEnvironment):
        """
        GIVEN a completed workflow run
        WHEN its history is replayed
        THEN the replay produces the same commands (no non-determinism error)
        """
        await run_workflow(env, FakeActivities())
        handle = env.client.get_workflow_handle(f"ingestion-job-{DOCUMENT_ID}")

        await Replayer(
            workflows=[DocumentIngestionWorkflow],
            data_converter=pydantic_data_converter,
        ).replay_workflow(await handle.fetch_history())


class TestFailedIngestion:
    """A failed processing step marks the document and the job as FAILED."""

    async def test_processing_failure_marks_document_and_job_failed(
        self, env: WorkflowEnvironment
    ):
        """
        GIVEN the processing activity fails permanently
        WHEN the workflow runs
        THEN it marks the document FAILED and the job FAILED with the error
        AND the workflow fails with the processing error
        """
        fakes = FakeActivities(fail_processing=True)

        with pytest.raises(WorkflowFailureError) as exc_info:
            await run_workflow(env, fakes)

        assert fakes.payload("update_document").status == "FAILED"
        job_update = fakes.payload("update_job")
        assert job_update.status == "FAILED"
        assert "parser exploded" in job_update.error_message
        assert "parser exploded" in str(exc_info.value.cause)

    async def test_compensation_failure_keeps_original_error(
        self, env: WorkflowEnvironment
    ):
        """
        GIVEN the processing activity fails
        AND the compensation (update document) also fails
        WHEN the workflow runs
        THEN the workflow fails with the original processing error,
        AND not with the compensation error
        """
        fakes = FakeActivities(fail_processing=True, fail_compensation=True)

        with pytest.raises(WorkflowFailureError) as exc_info:
            await run_workflow(env, fakes)

        message = str(exc_info.value.cause)
        assert "parser exploded" in message
        assert "database down" not in message
