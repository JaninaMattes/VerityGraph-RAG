"""Tests for the MinIO 'ObjectCreated' event handler."""

import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from src.infrastructure.message_broker.kafka.handler import MinioObjectCreatedHandler

pytestmark = pytest.mark.asyncio

TENANT_ID = "12bf3456-7d89-12d3-a456-78c91cf2b34f"
DOCUMENT_ID = "39b02a26-86d0-4dd6-ae6e-7a0ea578f290"
OBJECT_KEY = f"{TENANT_ID}/files/2026/01/{DOCUMENT_ID}.pdf"


def make_record(
    key: str = OBJECT_KEY,
    bucket: str = "files",
    metadata: dict[str, str] | None = None,
    **object_fields: Any,
) -> dict[str, Any]:
    """Build a MinIO S3 event record with sensible defaults."""
    if metadata is None:
        metadata = {
            "tenant-id": TENANT_ID,
            "filename": "report.pdf",
            "document-type": "pdf",
        }
    return {
        "eventName": "s3:ObjectCreated:Put",
        "s3": {
            "bucket": {"name": bucket},
            "object": {"key": key, "userMetadata": metadata, **object_fields},
        },
    }


@pytest.fixture
def temporal_client() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def handler(temporal_client: AsyncMock) -> MinioObjectCreatedHandler:
    return MinioObjectCreatedHandler(temporal_client, temporal_task_queue="test-queue")


class TestStartsIngestionWorkflow:
    """The handler starts exactly one ingestion workflow per valid upload."""

    async def test_valid_record_starts_workflow_with_payload(
        self, handler: MinioObjectCreatedHandler, temporal_client: AsyncMock
    ):
        """
        GIVEN a complete MinIO record for a PDF upload
        WHEN the handler handles the record
        THEN it starts 'DocumentIngestionWorkflow' with a deterministic workflow id
        AND the payload holds the record values
        """
        record = make_record(size=2048, eTag="abc", contentType="application/pdf")

        await handler.handle(record)

        temporal_client.start_workflow.assert_awaited_once()
        args, kwargs = temporal_client.start_workflow.call_args
        assert args[0] == "DocumentIngestionWorkflow"
        assert args[1] == {
            "document_id": DOCUMENT_ID,
            "tenant_id": TENANT_ID,
            "filename": "report.pdf",
            "bucket_name": "files",
            "object_key": OBJECT_KEY,
            "etag": "abc",
            "size_bytes": 2048,
            "mime_type": "application/pdf",
            "document_type": "PDF",
        }
        assert kwargs["id"] == f"ingestion-job-{DOCUMENT_ID}"
        assert kwargs["task_queue"] == "test-queue"
        assert (
            kwargs["id_reuse_policy"]
            == WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY
        )

    async def test_document_id_excludes_file_extension(
        self, handler: MinioObjectCreatedHandler, temporal_client: AsyncMock
    ):
        """
        GIVEN an object key that ends with '<document_id>.pdf'
        WHEN the handler handles the record
        THEN the payload document_id is the bare UUID without the extension
        """
        await handler.handle(make_record())

        payload = temporal_client.start_workflow.call_args.args[1]
        assert payload["document_id"] == DOCUMENT_ID
        uuid.UUID(payload["document_id"])  # must parse

    async def test_document_id_without_extension(
        self, handler: MinioObjectCreatedHandler, temporal_client: AsyncMock
    ):
        """
        GIVEN an object key without a file extension
        WHEN the handler handles the record
        THEN the payload document_id is the last key segment
        """
        await handler.handle(
            make_record(key=f"{TENANT_ID}/files/2026/01/{DOCUMENT_ID}")
        )

        assert (
            temporal_client.start_workflow.call_args.args[1]["document_id"]
            == DOCUMENT_ID
        )

    async def test_url_encoded_key_is_decoded(
        self, handler: MinioObjectCreatedHandler, temporal_client: AsyncMock
    ):
        """
        GIVEN an object key in which MinIO encoded '/' as '%2F'
        WHEN the handler handles the record
        THEN the payload object_key is the decoded key
        """
        await handler.handle(make_record(key=OBJECT_KEY.replace("/", "%2F")))

        assert (
            temporal_client.start_workflow.call_args.args[1]["object_key"] == OBJECT_KEY
        )

    async def test_missing_optional_fields_use_defaults(
        self, handler: MinioObjectCreatedHandler, temporal_client: AsyncMock
    ):
        """
        GIVEN a record without size, eTag, content type, filename and document type
        WHEN the handler handles the record
        THEN the payload uses the documented defaults
        """
        await handler.handle(make_record(metadata={"tenant-id": TENANT_ID}))

        payload = temporal_client.start_workflow.call_args.args[1]
        assert payload["size_bytes"] == -1
        assert payload["etag"] == ""
        assert payload["mime_type"] == "application/octet-stream"
        assert payload["filename"] == ""
        assert payload["document_type"] == "PDF"


class TestSkipsMalformedRecords:
    """The handler skips records that it can never process, without an error."""

    @pytest.mark.parametrize(
        ("record", "reason"),
        [
            (make_record(bucket=""), "missing bucket"),
            (make_record(key=""), "missing object key"),
            (make_record(metadata={}), "missing tenant id"),
            (make_record(key="tenant/files/2026/01/not-a-uuid.pdf"), "invalid id"),
            ({"eventName": "s3:ObjectCreated:Put"}, "missing s3 section"),
        ],
    )
    async def test_malformed_record_is_skipped(
        self,
        handler: MinioObjectCreatedHandler,
        temporal_client: AsyncMock,
        record: dict[str, Any],
        reason: str,
    ):
        """
        GIVEN a record with a missing or invalid required value
        WHEN the handler handles the record
        THEN it starts no workflow and raises no error
        """
        await handler.handle(record)

        temporal_client.start_workflow.assert_not_awaited()


class TestErrorHandling:
    """Duplicates are ignored; other errors propagate so that the consumer retries."""

    async def test_duplicate_workflow_is_ignored(
        self, handler: MinioObjectCreatedHandler, temporal_client: AsyncMock
    ):
        """
        GIVEN a workflow for the same document is already running
        WHEN the handler handles the record again
        THEN it raises no error
        """
        temporal_client.start_workflow.side_effect = WorkflowAlreadyStartedError(
            "ingestion-job", "DocumentIngestionWorkflow"
        )

        await handler.handle(make_record())

    async def test_temporal_failure_propagates(
        self, handler: MinioObjectCreatedHandler, temporal_client: AsyncMock
    ):
        """
        GIVEN Temporal is unreachable
        WHEN the handler handles a valid record
        THEN the original error propagates to the caller
        """
        temporal_client.start_workflow.side_effect = ConnectionError("temporal down")

        with pytest.raises(ConnectionError, match="temporal down"):
            await handler.handle(make_record())
