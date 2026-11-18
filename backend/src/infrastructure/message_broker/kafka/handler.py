"""Handler that turns a MinIO 'ObjectCreated' event into an ingestion workflow."""

import urllib.parse
from typing import Any

from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from src.domain.documents.dataclasses import StorageKey
from src.infrastructure.message_broker.provider import EventHandler
from src.infrastructure.workflow_execution.temporalio.models import IngestionPayload
from src.libs.core.logger import get_logger

logger = get_logger("kafka.event_handler")


class MinioObjectCreatedHandler(EventHandler):
    """Thin handler: Kafka is the trigger, Temporal owns the transaction.

    One upload starts one workflow with the id 'ingestion-job-<document_id>', so a
    duplicate event does not start a second run.
    """

    def __init__(
        self, temporal_client: Client, temporal_task_queue: str = "ingestion-task-queue"
    ) -> None:
        self.temporal_client = temporal_client
        self.temporal_task_queue = temporal_task_queue

    async def handle(self, record: dict[str, Any]) -> None:
        """Start the ingestion workflow for one S3 event record.

        A record without bucket, key or tenant id, or with a key that holds no document
        id, is logged and skipped. A duplicate workflow is ignored. Any other error
        (for example Temporal is unreachable) propagates, so the consumer retries.
        """
        s3 = record.get("s3", {})
        bucket = s3.get("bucket", {}).get("name", "")
        s3_object = s3.get("object", {})
        object_key = urllib.parse.unquote(s3_object.get("key", ""))
        metadata = s3_object.get("userMetadata", {})
        tenant_id = metadata.get("tenant-id")

        if not bucket or not object_key or not tenant_id:
            logger.error("Skipping S3 record without bucket, object key or tenant id.")
            return
        try:
            document_id = StorageKey(object_key).document_id
        except ValueError:
            logger.error("Skipping S3 record: key %s holds no document id.", object_key)
            return

        payload = IngestionPayload(
            document_id=str(document_id),
            tenant_id=str(tenant_id),
            filename=metadata.get("filename", ""),
            bucket_name=bucket,
            object_key=object_key,
            etag=s3_object.get("eTag", ""),
            size_bytes=s3_object.get("size", -1),
            mime_type=s3_object.get("contentType", "application/octet-stream"),
            document_type=metadata.get("document-type", "PDF").upper(),
        )
        workflow_id = f"ingestion-job-{document_id}"
        try:
            await self.temporal_client.start_workflow(
                "DocumentIngestionWorkflow",
                payload.model_dump(mode="json"),
                id=workflow_id,
                task_queue=self.temporal_task_queue,
                id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
            )
            logger.info("Started workflow %s.", workflow_id)
        except WorkflowAlreadyStartedError:
            logger.info(
                "Workflow %s exists already. Ignoring duplicate event.", workflow_id
            )
