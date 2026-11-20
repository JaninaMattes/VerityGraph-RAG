"""Composition root of the background worker.

One process runs the Temporal worker (ingestion workflow and activities) and the Kafka
consumer that starts workflows for new uploads. Start it with
`python -m src.infrastructure.message_broker.kafka.worker`.
"""

import asyncio
import signal
from collections.abc import Coroutine
from contextlib import AsyncExitStack
from datetime import timedelta
from typing import Any

from aiokafka import AIOKafkaConsumer
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from src.infrastructure.database.postgres.engine import create_async_db_engine
from src.infrastructure.database.postgres.session import create_session_factory
from src.infrastructure.message_broker.kafka.handler import MinioObjectCreatedHandler
from src.infrastructure.message_broker.kafka.manager import KafkaEventManager
from src.infrastructure.parsing.docling import create_docling_chunker
from src.infrastructure.storage.client import create_storage_client
from src.infrastructure.storage.service import create_storage_service
from src.infrastructure.workflow_execution.temporalio.activities import (
    IngestFileActivities,
)
from src.infrastructure.workflow_execution.temporalio.workflows import (
    DocumentIngestionWorkflow,
    processing_task_queue,
)
from src.libs.core.config import Settings, get_settings
from src.libs.core.logger import get_logger, setup_logging

logger = get_logger(__name__)

EVENT_TYPES = ("s3:ObjectCreated:Put", "s3:ObjectCreated:CompleteMultipartUpload")


def create_consumer(settings: Settings) -> AIOKafkaConsumer:
    """Create the Kafka consumer. Auto commit is off: the manager commits after success."""
    return AIOKafkaConsumer(
        *settings.kafka_topics,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_group_id,
        enable_auto_commit=False,
        auto_offset_reset=settings.kafka_auto_offset_reset,
        max_poll_interval_ms=300000,
        session_timeout_ms=30000,
    )


def install_signal_handlers(stop_event: asyncio.Event) -> None:
    """Set `stop_event` on SIGTERM or SIGINT. Platforms without signals are tolerated."""
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            logger.warning("Signal handlers are not supported on this platform.")


async def run_until_stopped(
    consumer: Coroutine[Any, Any, None], stop_event: asyncio.Event
) -> None:
    """Run `consumer` until `stop_event` is set, then cancel it.

    If the consumer fails first, its error propagates, so the process exits and the
    container restarts instead of running without a consumer.
    """
    consumer_task = asyncio.create_task(consumer)
    stop_task = asyncio.create_task(stop_event.wait())
    done, pending = await asyncio.wait(
        {consumer_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
    )
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    if consumer_task in done:
        consumer_task.result()


async def main() -> None:
    """Wire the infrastructure and run until a stop signal or a consumer failure."""
    settings = get_settings()
    setup_logging(settings.log_level, json_logs=settings.log_json)
    async with AsyncExitStack() as stack:
        db_engine = create_async_db_engine(settings)
        stack.push_async_callback(db_engine.dispose)

        storage = create_storage_service(create_storage_client(settings), settings)
        chunker = create_docling_chunker(
            tokenizer_model=settings.chunk_tokenizer_model,
            max_tokens=settings.chunk_max_tokens,
            do_ocr=settings.docling_do_ocr,
            max_pages=settings.max_document_pages,
            max_bytes=settings.max_upload_bytes,
        )
        activities = IngestFileActivities(
            create_session_factory(db_engine),
            storage,
            chunker,
            max_file_bytes=settings.max_upload_bytes,
        )
        temporal_client = await Client.connect(
            settings.temporal_url,
            namespace=settings.temporal_default_namespace,
            data_converter=pydantic_data_converter,
        )
        temporal_worker = Worker(
            temporal_client,
            task_queue=settings.temporal_task_queue,
            workflows=[DocumentIngestionWorkflow],
            activities=[
                activities.create_document_activity,
                activities.update_document_activity,
                activities.create_ingestion_job_activity,
                activities.update_ingestion_job_activity,
            ],
            # Allow in-flight activities to finish before forceful cancellation
            graceful_shutdown_timeout=timedelta(seconds=30),
        )
        # Parsing holds the Docling models and the page images in memory; this
        # worker takes only as many files as it can parse at the same time.
        parse_worker = Worker(
            temporal_client,
            task_queue=processing_task_queue(settings.temporal_task_queue),
            activities=[activities.process_document_activity],
            max_concurrent_activities=settings.max_concurrent_parses,
            graceful_shutdown_timeout=timedelta(seconds=30),
        )

        event_manager = KafkaEventManager(create_consumer(settings))
        handler = MinioObjectCreatedHandler(
            temporal_client, settings.temporal_task_queue
        )
        for event_type in EVENT_TYPES:
            event_manager.register_handler(event_type, handler)

        stop_event = asyncio.Event()
        install_signal_handlers(stop_event)
        async with temporal_worker, parse_worker:
            logger.info(
                "Worker running on task queue %s.", settings.temporal_task_queue
            )
            await run_until_stopped(event_manager.run(), stop_event)

    logger.info("Worker shutdown completed.")


if __name__ == "__main__":
    asyncio.run(main())
