# src/infrastructure/message_broker/kafka/worker.py

import asyncio
import signal
from contextlib import AsyncExitStack
from datetime import timedelta

from temporalio.client import Client
from temporalio.worker import Worker

from src.infrastructure.database.postgres.engine import create_async_db_engine
from src.infrastructure.database.postgres.session import create_session_factory
from src.infrastructure.message_broker.kafka.handler import MinioObjectCreatedHandler
from src.infrastructure.message_broker.kafka.manager import KafkaEventManager
from src.infrastructure.storage.client import create_storage_client
from src.infrastructure.storage.service import create_storage_service
from src.infrastructure.workflow_execution.temporalio.activities import (
    IngestFileActivities,
)
from src.infrastructure.workflow_execution.temporalio.workflows import (
    DocumentIngestionWorkflow,
)
from src.libs.core.config import get_settings
from src.libs.core.logger import get_logger
from src.pipelines.ingestion.pipeline import IngestionPipeline

logger = get_logger("kafka.run_worker")

""" Composition root that handles the concrete implementations of the 
    infrastructure elements in the application.
"""


async def main() -> None:
    logger.info("Starting Background Kafka Worker...")
    settings = get_settings()

    async with AsyncExitStack() as stack:
        # Initialize Core Infrastructure & Register Cleanup
        db_engine = create_async_db_engine(settings)
        stack.push_async_callback(db_engine.dispose)

        session_factory = create_session_factory(db_engine)
        minio_client = create_storage_client(settings)
        minio_storage = create_storage_service(minio_client, settings)

        # Compose the Ingestion Pipeline
        ingestion_pipeline = IngestionPipeline()

        # Connect to Temporal & Create Worker
        temporal_client = await Client.connect(
            settings.temporal_url, namespace=settings.temporal_default_namespace
        )
        ingestion_activities = IngestFileActivities(
            session_factory=session_factory,
            storage=minio_storage,
            ingestion_pipeline=ingestion_pipeline,
        )
        temporal_worker = Worker(
            temporal_client,
            task_queue=settings.temporal_task_queue,
            workflows=[DocumentIngestionWorkflow],
            activities=[
                ingestion_activities.create_document_activity,
                ingestion_activities.update_document_activity,
                ingestion_activities.create_ingestion_job_activity,
                ingestion_activities.update_ingestion_job_activity,
                ingestion_activities.process_document_activity,
            ],
            # Allow in-flight activities to finish before forceful cancellation
            graceful_shutdown_timeout=timedelta(seconds=30),
        )
        logger.info(
            "Temporal Worker started on task queue %s. ", settings.temporal_task_queue
        )

        # Initialize Kafka Event Manager and register MinIO object events
        num_kafka_workers = settings.kafka_num_workers
        event_manager = KafkaEventManager(
            num_workers=num_kafka_workers,
        )
        event_handler = MinioObjectCreatedHandler(
            temporal_client, temporal_task_queue=settings.temporal_task_queue
        )
        event_manager.register_handler("s3:ObjectCreated:Put", event_handler)
        event_manager.register_handler(
            "s3:ObjectCreated:CompleteMultipartUpload", event_handler
        )

        # Setup Shutdown Handling (SIGTERM/SIGINT)
        stop_event = asyncio.Event()

        def signal_handler():
            logger.info("Shutdown signal received. Stopping worker gracefully.")
            stop_event.set()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, signal_handler)
            except NotImplementedError:
                logger.warning(
                    "Signal handlers not supported on this platform (e.g., Windows)."
                )

        # Start Kafka Consumer as a background task
        kafka_task = asyncio.create_task(
            event_manager.start(
                settings.kafka_topics,
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id=settings.kafka_group_id,
                enable_auto_commit=settings.kafka_enable_auto_commit,
                auto_offset_reset=settings.kafka_auto_offset_reset,
            )
        )
        logger.info("Kafka Consumer started.")

        # Run Temporal Worker and Wait for Shutdown Signal
        async with temporal_worker:
            logger.info(
                "Temporal Worker started on task queue: %s.",
                settings.temporal_task_queue,
            )
            # Block until SIGTERM/SIGINT is received
            await stop_event.wait()

        # Ordered Cleanup: Stop Kafka before exiting the AsyncExitStack
        logger.info("Stopping Kafka Consumer...")
        await event_manager.stop()

        # Ensure the kafka task is fully resolved and cleaned up
        if not kafka_task.done():
            kafka_task.cancel()
            try:
                await kafka_task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Error while stopping Kafka consumer loop task.")

    logger.info("Background Worker shutdown completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
