"""Kafka consumer loop with at-least-once delivery."""

import asyncio
import json
from typing import Any

from aiokafka import AIOKafkaConsumer, TopicPartition

from src.infrastructure.message_broker.provider import EventHandler
from src.libs.core.logger import get_logger

logger = get_logger(__name__)


class KafkaEventManager:
    """Consume MinIO notifications and route each record to its event handler.

    Delivery is at least once: the offset of a message is committed only after all of
    its records are handled. If handling fails, the consumer seeks back to that message
    and retries it after `retry_delay_seconds`; the other partitions continue.
    Handlers must therefore be idempotent. A message that is not a JSON object with a
    'Records' list is logged and skipped, so it cannot block its partition.

    Scale out by adding partitions and running more worker processes; one process runs
    one consumer loop.
    """

    def __init__(
        self, consumer: AIOKafkaConsumer, retry_delay_seconds: float = 1.0
    ) -> None:
        self._consumer = consumer
        self._retry_delay_seconds = retry_delay_seconds
        self._handlers: dict[str, EventHandler] = {}

    def register_handler(self, event_type: str, handler: EventHandler) -> None:
        """Route records whose 'eventName' equals `event_type` to `handler`."""
        self._handlers[event_type] = handler

    async def run(self) -> None:
        """Consume until cancelled. A fatal consumer error propagates.

        The consumer is started on entry and always stopped on exit.
        """
        await self._consumer.start()
        logger.info("Kafka consumer started.")
        try:
            while True:
                batch = await self._consumer.getmany(timeout_ms=1000, max_records=10)
                for partition, messages in batch.items():
                    await self._process_partition(partition, messages)
        finally:
            await self._consumer.stop()
            logger.info("Kafka consumer stopped.")

    async def _process_partition(
        self, partition: TopicPartition, messages: list[Any]
    ) -> None:
        for message in messages:
            try:
                await self._dispatch(message)
            except Exception:
                logger.exception(
                    "Failed to handle offset %s of %s. Retrying.",
                    message.offset,
                    partition,
                )
                self._consumer.seek(partition, message.offset)
                await asyncio.sleep(self._retry_delay_seconds)
                return
            await self._consumer.commit({partition: message.offset + 1})

    async def _dispatch(self, message: Any) -> None:
        try:
            payload = json.loads(message.value)
        except ValueError:  # also covers UnicodeDecodeError
            logger.error(
                "Skipping offset %s: the value is not valid JSON.", message.offset
            )
            return
        records = payload.get("Records") if isinstance(payload, dict) else None
        if not records:
            logger.warning(
                "Skipping offset %s: no 'Records' in the message.", message.offset
            )
            return

        for record in records:
            event_type = record.get("eventName", "")
            handler = self._handlers.get(event_type)
            if handler is None:
                logger.info("No handler for event %s. Skipping the record.", event_type)
                continue
            await handler.handle(record)
