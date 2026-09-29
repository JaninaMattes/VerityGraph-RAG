import urllib.parse
from typing import Any

from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

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

                s3_data = record.get("s3", {})
                bucket = s3_data.get("bucket", {}).get("name")
                raw_object_key = s3_data.get("object", {}).get("key")

                if not bucket or not raw_object_key:
                    logger.error(
                        "Malformed record skipped. Missing bucket name or object key."
                    )
                    continue

                # Unquote URL characters (%2F to /)
                object_key = urllib.parse.unquote(raw_object_key)
                key_parts = object_key.split("/")

                # Target format: {bucket-name}/{tenant_id}/{namespace}/{year}/{month}/{document_id}
                if len(key_parts) < 5:
                    logger.error(
                        "Invalid key path sequence for object key: %s. Expected at least 5 segments.",
                        object_key,
                    )
                    continue

                # Slice end to exact document UUID string
                document_id = key_parts[-1]
                logger.info(
                    "Extracted document id: %s from object path: %s",
                    document_id,
                    object_key,
                )

                try:
                    # Start Ingestion Workflow
                    workflow_id = f"ingestion-job-{document_id}"  # Create trackable deterministic workflow_id
                    await self.temporal_client.start_workflow(
                        "DocumentIngestionWorkflow",  # Must match @workflow.defn name
                        {
                            "document_id": str(document_id),
                            "bucket": bucket,
                            "object_key": object_key,
                            "size": s3_data["object"].get(
                                "size", -1
                            ),  # negative values are treated as unknown size
                            "mime_type": s3_data["object"].get(
                                "contentType", "application/octet-stream"
                            ),
                        },
                        id=workflow_id,
                        task_queue=self.temporal_task_queue,
                        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
                    )
                    logger.info(
                        "Successfully triggered Temporal workflow with id: %s",
                        workflow_id,
                    )
                except WorkflowAlreadyStartedError:
                    # Deduplicate event pipeline
                    logger.info(
                        "Workflow already exists for document with id %s. Ignoring duplicate event.",
                        document_id,
                    )

        except Exception as exc:
            failed_key = payload.get("Key", "Unknown-Payload-Key")
            logger.exception(
                "System failure when handling MinIO 'ObjectCreated' events for document with Key:  %s",
                failed_key,
            )
            raise EventHandlerException(
                "Failed to handle incoming MinIO 'ObjectCreated' events."
            ) from exc