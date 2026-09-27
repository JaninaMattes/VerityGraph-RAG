import asyncio
import signal
import sys

from temporalio.client import Client

from src.infrastructure.message_broker.kafka.handler import MinioObjectCreatedHandler
from src.infrastructure.message_broker.kafka.manager import KafkaEventManager
from src.shared.core.config import get_settings
from src.shared.core.logger import get_logger

logger = get_logger("kafka.worker")


async def main() -> None:
    logger.info("Starting Background Kafka Worker...")

    # Connect to Temporal
    try:
        settings = get_settings()
        temporal_client = await Client.connect(
            settings.temporal_url, namespace=settings.temporal_default_namespace
        )
        logger.info("Connected to Temporal client...")
    except Exception:
        logger.exception("Failed to connect to Temporal. Exiting.")
        sys.exit(1)

    # Initialize Kafka Event Manager
    kafka_event_manager = KafkaEventManager(
        temporal_client,
        num_workers=2,  # number of concurrent polling loops
    )

    # Initialise the MinIO Event Handler
    minio_event_handler = MinioObjectCreatedHandler(
        temporal_client, temporal_task_queue=settings.temporal_task_queue
    )
    kafka_event_manager.register_handler("s3:ObjectCreated:Put", minio_event_handler)
    kafka_event_manager.register_handler(
        "s3:ObjectCreated:CompleteMultipartUpload", minio_event_handler
    )
    kafka_event_manager.register_handler("s3:ObjectCreated:Delete", minio_event_handler)

    # Start the Kafka Consumer Loop
    try:
        await kafka_event_manager.start(
            settings.kafka_topics,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id=settings.kafka_group_id,
            enable_auto_commit=settings.kafka_enable_auto_commit,
            auto_offset_reset=settings.kafka_auto_offset_reset,
        )

    except Exception:
        logger.exception("Failed to start the Kafka Consumer. Exiting the application.")
        sys.exit(1)

    stop_event = asyncio.Event()

    def signal_handler():
        logger.info("Shutdown signal received. Stopping worker gracefully.")
        stop_event.set()

    # TODO: Register signal handlers for Docker SIGTERM
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    await stop_event.wait()
    await kafka_event_manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
