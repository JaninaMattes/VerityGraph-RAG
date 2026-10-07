# src/infrastructure/message_broker/kafka/handler.py

import urllib.parse

from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from src.infrastructure.message_broker.provider import EventHandler
from src.infrastructure.workflow_execution.temporalio.models import IngestionPayload
from src.libs.core.logger import get_logger
from src.libs.exceptions.exceptions import EventHandlerException

logger = get_logger("kafka.event_handler")


class MinioObjectCreatedHandler(EventHandler):
    def __init__(
        self,
        temporal_client: Client,
        temporal_task_queue: str = "ingestion-task-queue",
    ) -> None:
        """Responsible for handling the business logic.
        Thin Handler, Fat Orchestrator: Kafka defined the trigger, whereas Temporal defines the transaction manager.
        """
        super().__init__()
        self.temporal_client = temporal_client
        self.temporal_task_queue = temporal_task_queue

    async def handle(
        self,
        record: dict,
    ) -> None:
        """Iterate through records and route them based on 'eventName'."""
        try:
            event_name = record.get("eventName", "")
            if "ObjectCreated" not in event_name:
                logger.warning(
                    "Expected event 'ObjectCreated' not in event name. Skipping: %s",
                    event_name,
                )
                return

            s3_data = record.get("s3", {})
            bucket = s3_data.get("bucket", {}).get("name", "")
            raw_object_key = s3_data.get("object", {}).get("key", "")

            if not bucket or not raw_object_key:
                logger.error(
                    "Malformed Kafka record. Missing bucket 'name' or object 'key' value."
                )
                return

            # Unquote URL characters (%2F to /)
            object_key = urllib.parse.unquote(raw_object_key)
            document_id = object_key.split("/")[
                -1
            ]  # TODO: Improve this to be more robust
            logger.info(
                "Extracted document id: %s from MinIO object key: %s",
                document_id,
                object_key,
            )

            ingestion_payload = IngestionPayload(
                document_id=str(document_id),
                bucket=bucket,
                object_key=object_key,
                etag=s3_data.get("object", {}).get("eTag", ""),
                size_bytes=s3_data.get("object", {}).get("size", -1),
                mime_type=s3_data.get("object", {}).get(
                    "contentType", "application/octet-stream"
                ),
            )

            # Start Ingestion Workflow
            workflow_id = f"ingestion-job-{document_id}"  # Create trackable deterministic workflow_id
            try:
                await self.temporal_client.start_workflow(
                    "DocumentIngestionWorkflow",
                    ingestion_payload.model_dump(
                        mode="json"
                    ),  # Serialize for network transport
                    id=workflow_id,
                    task_queue=self.temporal_task_queue,
                    id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
                )
                logger.info("Triggered Temporal workflow: %s", workflow_id)

            except WorkflowAlreadyStartedError:
                logger.info(
                    "Workflow %s already exists. Ignoring duplicate event.", workflow_id
                )
        except Exception as exc:
            logger.exception("System failure handling MinIO event.")
            raise EventHandlerException("Failed to handle MinIO event.") from exc
