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
    settings = get_settings()

    # Connect to Temporal
    try:
        temporal_client = await Client.connect(
            settings.temporal_url, namespace=settings.temporal_default_namespace
        )
        logger.info("Connected to Temporal server.")
    except Exception:
        logger.exception("Failed to connect to Temporal server. Exiting.")
        sys.exit(1)

    # TODO: Activate Temporal Worker

    # Initialize Kafka Event Manager and register supported MinIO object events
    event_manager = KafkaEventManager(
        temporal_client,
        num_workers=2,
    )

    event_handler = MinioObjectCreatedHandler(
        temporal_client, temporal_task_queue=settings.temporal_task_queue
    )
    event_manager.register_handler("s3:ObjectCreated:Put", event_handler)
    event_manager.register_handler(
        "s3:ObjectCreated:CompleteMultipartUpload", event_handler
    )
    event_manager.register_handler("s3:ObjectRemoved:Delete", event_handler)

    # Start Kafka Consumer as non-blocking task
    try:
        kafka_task = asyncio.create_task(
            event_manager.start(
                settings.kafka_topics,
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id=settings.kafka_group_id,
                enable_auto_commit=settings.kafka_enable_auto_commit,
                auto_offset_reset=settings.kafka_auto_offset_reset,
            )
        )

    except Exception:
        logger.exception("Failed to start the Kafka Consumer. Exiting the application.")
        sys.exit(1)

    # Register signal handlers for Docker SIGTERM
    stop_event = asyncio.Event()

    def signal_handler():
        logger.info("Shutdown signal received. Stopping worker gracefully.")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    # Wait until Docker or a user sends a termination signal
    await stop_event.wait()

    # Stop Kafka first to freeze incoming traffic
    await event_manager.stop()
    try:
        await kafka_task  # Await it to ensure underlying loops break cleanly
    except Exception:
        logger.exception("Error while stopping Kafka consumer loop task.")

    logger.info("Background Worker shutdown completed successfully.")

if __name__ == "__main__":
    asyncio.run(main())
