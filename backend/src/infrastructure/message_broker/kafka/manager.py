# src/infrastructure/message_broker/kafka/manager.py

import asyncio
import json
from typing import Any

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import (
    KafkaConnectionError,
    OffsetOutOfRangeError,
    TopicAuthorizationFailedError,
)
from temporalio.client import Client

from src.infrastructure.message_broker.provider import EventHandler
from src.libs.core.logger import get_logger
from src.libs.exceptions.exceptions import (
    AIOKafkaConsumerAuthException,
    AIOKafkaConsumerException,
    AIOKafkaConsumerOffsetException,
    EventHandlerException,
    EventHandlerNotRegisterdException,
)

logger = get_logger("kafka.manager")


class KafkaEventManager:
    """Manages Kafka event consumption and routing to appropriate handlers."""

    def __init__(self, temporal_client: Client, num_workers: int = 2) -> None:
        """Initialize the Kafka event manager"""

        self.temporal_client: Client = temporal_client
        self.num_workers = num_workers
        self.tasks: list[asyncio.Task] = []
        self.event_handlers: dict[str, EventHandler] = {}
        self.consumer: AIOKafkaConsumer | None = None
        self._is_running = False

    def register_handler(self, event_type: str, handler: EventHandler) -> None:
        """Register a handler for a specific event type"""
        self.event_handlers[event_type] = handler

    async def start(
        self,
        topics: list[str],
        bootstrap_servers: str,
        group_id: str,
        enable_auto_commit: bool = False,
        auto_offset_reset: str = "earliest",
    ) -> None:
        """Start the Kafka event manager by connecting to Temporal and Kafka KRaft
        before starting the consumer."""

        try:
            # Start the consumer
            self.consumer = AIOKafkaConsumer(
                *topics,
                bootstrap_servers=bootstrap_servers,
                group_id=group_id,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                enable_auto_commit=enable_auto_commit,  # Manual commit for at-least-once delivery
                auto_offset_reset=auto_offset_reset,
                max_poll_interval_ms=300000,
                session_timeout_ms=30000,
            )
            await self.consumer.start()  # Connect to Kafka KRaft cluster
            self._is_running = True
            logger.info(
                "Kafka consumer started. Spawning %s workers.", self.num_workers
            )

            # Start multiple worker tasks for parallel message processing.
            for idx in range(self.num_workers):
                task = asyncio.create_task(self._consume(idx))
                self.tasks.append(task)

        except KafkaConnectionError:
            logger.exception("Failed to connect and start AIOKafkaConsumer.")
            raise

    async def _consume(self, worker_id) -> None:
        """
        Get messages from assigned topics / partitions:
        async getmany(): Prefetched messages are returned in batches by topic-partition.
        If messages is not available in the prefetched buffer this method waits timeout_ms milliseconds.
        """
        logger.info(f"Starting consumer worker {worker_id}")
        try:
            # Each worker continuously consumes messages from assigned Kafka topics / partitions.
            while self._is_running and self.consumer:
                try:
                    # Fetch one batch of messages from the consumer.
                    # (timeout_ms defines ms spent waiting if data is not available in the buffer)
                    data = await self.consumer.getmany(timeout_ms=1000, max_records=10)
                    for messages in data.values():
                        for message in messages:
                            try:
                                await self._process_message(message)
                            except Exception:
                                logger.exception(
                                    "Handler failed to process message for offset %s.",
                                    message.offset,
                                )

                    # Commit offsets to Kafka after the batch is processed
                    if data:
                        await self.consumer.commit()
                    else:
                        logger.info("No messages received.")
                        await asyncio.sleep(1)  # idle

                except asyncio.CancelledError:
                    logger.warning(
                        "The Kafka consumer worker %s was cancelled.", worker_id
                    )
                    raise
                except TopicAuthorizationFailedError as exc:
                    logger.exception(
                        "The Kafka consumer worker %s failed with authorization error. The Kafka topic requires authorisation.",
                        worker_id,
                    )
                    topics = await self.consumer.topics()
                    raise AIOKafkaConsumerAuthException(topics) from exc
                except OffsetOutOfRangeError as exc:
                    logger.exception(
                        "The Kafka consumer worker %s failed with an offset out of range error. The 'auto_offset_reset' policy has not been set.",
                        worker_id,
                    )
                    raise AIOKafkaConsumerOffsetException() from exc

        except Exception as exc:
            logger.exception(
                "An error occurred while fetching messages with the Kafka consumer worker %s from the assigned topics or paritions.",
                worker_id,
            )
            raise AIOKafkaConsumerException(
                "An error occurred while fetching messages from Kafka."
            ) from exc
        finally:
            logger.info(
                "The Kafka consumer worker %s has finished processing and is shutting down.",
                worker_id,
            )

    async def _process_message(self, message: Any) -> None:
        """MinIO S3 sends a batch of records which are processed and routed one by one."""
        records = message.value.get("Records", [])

        if not records:
            logger.warning(
                "Mallformed message! Received Kafka message with empty 'Records' array."
            )
            return

        for record in records:
            event_type = record.get("eventName", "unknownEvent")
            handler = self.event_handlers.get(event_type)

            if handler:
                try:
                    await handler.handle(record)
                except EventHandlerException:
                    logger.exception(
                        "Handler failed for event: %s. Sending to DLQ.", event_type
                    )
                    # Log and send to DLQ. Do not crash the worker.
                    await self._send_to_dlq(message, record)
            else:
                logger.exception(
                    "No handler registered for event type: %s. Skipping this record.",
                    event_type,
                )
                raise EventHandlerNotRegisterdException(event_type)

    async def _send_to_dlq(self, message: Any, record: Any) -> None:
        logger.warning(
            f"DLQ Placeholder: Message at offset {message.offset} failed processing."
        )

    async def stop(self) -> None:
        logger.info("Stopping Kafka event manager....")

        self._is_running = False
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        if self.consumer:
            await self.consumer.stop()

        logger.info("Kafka consumer worker stopped.")