import urllib.parse
import uuid
from typing import Any

from temporalio.client import Client

from src.infrastructure.message_broker.provider import EventHandler
from src.shared.core.logger import get_logger
from src.shared.exception.exceptions import EventHandlerException

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
        payload: dict[str, Any],
    ) -> None:
        logger.info("Processing MinIO 'ObjectCreated' events.")
        try:
            for record in payload.get("Records", []):
                event_name = record.get("eventName", "")

                if "ObjectCreated" not in event_name:
                    logger.info(
                        "Expected event 'ObjectCreated' not in event name. Skipping: %s",
                        event_name,
                    )
                    continue

                bucket = record["s3"]["bucket"]["name"]
                raw_object_key = record["s3"]["object"]["key"]

                # Unquote URL characters (%2F -> /)
                object_key = urllib.parse.unquote(raw_object_key)
                key_parts = object_key.split("/")

                # Target format: {bucket-name}/{tenant_id}/{namespace}/{year}/{month}/{document_id}
                # Safe structure validation: Verify it contains your structured segments
                if len(key_parts) < 5:
                    logger.error(
                        "Invalid key path sequence for object key: %s. Expected at least 5 segments.",
                        object_key,
                    )
                    continue

                # Safely slice from the end to get the exact document UUID string
                document_id = key_parts[-1]

                logger.info(
                    "Extracted Document ID: %s from object path: %s",
                    document_id,
                    object_key,
                )

                # Workflow 2:
                workflow_id = f"ingestion-job-{object_key}"  # Create trackable deterministic workflow_id
                await self.temporal_client.start_workflow(
                    "DocumentIngestionWorkflow",  # Must match @workflow.defn name
                    args=[
                        {
                            "document_id": str(document_id),
                            "bucket": bucket,
                            "object_key": object_key,
                            "size": record["s3"]["object"].get("size", 0),
                            "mime_type": record["s3"]["object"].get(
                                "contentType", "application/octet-stream"
                            ),
                        }
                    ],
                    id=workflow_id,
                    task_queue=self.temporal_task_queue,
                )
                logger.info(
                    "Successfully triggered Temporal workflow with id: %s", workflow_id
                )

        except Exception as exc:
            logger.exception(
                "System failure when handling MinIO 'ObjectCreated' events for document with Key:  %s",
                payload["Key"],
            )
            raise EventHandlerException(
                "Failed to handle incoming MinIO 'ObjectCreated' events."
            ) from exc
