"""Tests for the Kafka event manager (consume, route, commit, retry)."""

import asyncio
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiokafka import TopicPartition

from src.infrastructure.message_broker.kafka.manager import KafkaEventManager

PUT = "s3:ObjectCreated:Put"
TP0 = TopicPartition("minio-events", 0)
TP1 = TopicPartition("minio-events", 1)


def message(
    offset: int, *event_names: str, raw: bytes | None = None
) -> SimpleNamespace:
    """Build a Kafka message whose value is a MinIO notification with the given events."""
    if raw is None:
        raw = json.dumps(
            {"Records": [{"eventName": name} for name in event_names]}
        ).encode()
    return SimpleNamespace(offset=offset, value=raw)


def make_consumer(*batches: dict[TopicPartition, list[Any]]) -> MagicMock:
    """A consumer that returns the batches in order and then stops the loop."""
    consumer = MagicMock()
    consumer.start = AsyncMock()
    consumer.stop = AsyncMock()
    consumer.commit = AsyncMock()
    consumer.getmany = AsyncMock(side_effect=[*batches, asyncio.CancelledError()])
    return consumer


async def run_until_cancelled(manager: KafkaEventManager) -> None:
    with pytest.raises(asyncio.CancelledError):
        await manager.run()


@pytest.fixture
def handler() -> AsyncMock:
    return AsyncMock()


@pytest.fixture(autouse=True)
def no_sleep():
    """Skip the retry delay so that the tests run fast."""
    with patch(
        "src.infrastructure.message_broker.kafka.manager.asyncio.sleep", new=AsyncMock()
    ) as sleep:
        yield sleep


class TestLifecycle:
    """The manager owns the consumer connection for the duration of run()."""

    async def test_run_starts_and_stops_consumer(self):
        """
        GIVEN a manager with a consumer
        WHEN run() is cancelled
        THEN the consumer was started once and stopped once
        """
        consumer = make_consumer()

        await run_until_cancelled(KafkaEventManager(consumer))

        consumer.start.assert_awaited_once()
        consumer.stop.assert_awaited_once()

    async def test_consumer_is_stopped_when_polling_fails(self):
        """
        GIVEN a consumer whose poll raises a fatal error
        WHEN run() is called
        THEN the error propagates AND the consumer is stopped
        """
        consumer = make_consumer()
        consumer.getmany.side_effect = RuntimeError("broker gone")

        with pytest.raises(RuntimeError, match="broker gone"):
            await KafkaEventManager(consumer).run()

        consumer.stop.assert_awaited_once()


class TestRouting:
    """Records are routed to the handler that is registered for their event name."""

    async def test_registered_event_is_handled_and_committed(self, handler: AsyncMock):
        """
        GIVEN a handler registered for 'ObjectCreated:Put'
        WHEN a message with one such record arrives
        THEN the handler receives the record AND the next offset is committed
        """
        consumer = make_consumer({TP0: [message(7, PUT)]})
        manager = KafkaEventManager(consumer)
        manager.register_handler(PUT, handler)

        await run_until_cancelled(manager)

        handler.handle.assert_awaited_once_with({"eventName": PUT})
        consumer.commit.assert_awaited_once_with({TP0: 8})

    async def test_every_record_in_a_message_is_handled(self, handler: AsyncMock):
        """
        GIVEN a message with two records
        WHEN the message is processed
        THEN the handler receives both records in order
        """
        consumer = make_consumer({TP0: [message(0, PUT, PUT)]})
        manager = KafkaEventManager(consumer)
        manager.register_handler(PUT, handler)

        await run_until_cancelled(manager)

        assert handler.handle.await_count == 2

    async def test_unregistered_event_is_skipped_and_committed(
        self, handler: AsyncMock
    ):
        """
        GIVEN a handler registered only for 'ObjectCreated:Put'
        WHEN a message with an 'ObjectRemoved' record arrives
        THEN the handler is not called AND the message is committed
        """
        consumer = make_consumer({TP0: [message(3, "s3:ObjectRemoved:Delete")]})
        manager = KafkaEventManager(consumer)
        manager.register_handler(PUT, handler)

        await run_until_cancelled(manager)

        handler.handle.assert_not_awaited()
        consumer.commit.assert_awaited_once_with({TP0: 4})

    @pytest.mark.parametrize(
        "raw",
        [b"not json", b"\xff\xfe", b"[1, 2]", b'{"Records": []}', b"{}"],
        ids=[
            "invalid-json",
            "invalid-utf8",
            "not-an-object",
            "empty-records",
            "no-records",
        ],
    )
    async def test_unusable_message_is_skipped_and_committed(
        self, handler: AsyncMock, raw: bytes
    ):
        """
        GIVEN a message that can never be processed (poison message)
        WHEN the message arrives
        THEN the handler is not called AND the message is committed, so it does not block
        """
        consumer = make_consumer({TP0: [message(5, raw=raw)]})
        manager = KafkaEventManager(consumer)
        manager.register_handler(PUT, handler)

        await run_until_cancelled(manager)

        handler.handle.assert_not_awaited()
        consumer.commit.assert_awaited_once_with({TP0: 6})


class TestAtLeastOnceDelivery:
    """A failed message is not committed; it is fetched again after a delay."""

    async def test_failed_message_is_retried_and_not_committed(
        self, handler: AsyncMock, no_sleep: AsyncMock
    ):
        """
        GIVEN a handler that fails for the message at offset 1
        WHEN a batch with offsets 0, 1, 2 is processed
        THEN offset 0 is committed, offset 1 is not committed
        AND the consumer seeks back to offset 1 after the retry delay
        AND offset 2 is not processed in this batch
        """
        handler.handle.side_effect = [None, RuntimeError("temporal down")]
        consumer = make_consumer(
            {TP0: [message(0, PUT), message(1, PUT), message(2, PUT)]}
        )
        manager = KafkaEventManager(consumer, retry_delay_seconds=2.5)
        manager.register_handler(PUT, handler)

        await run_until_cancelled(manager)

        consumer.commit.assert_awaited_once_with({TP0: 1})
        consumer.seek.assert_called_once_with(TP0, 1)
        no_sleep.assert_awaited_once_with(2.5)
        assert handler.handle.await_count == 2

    async def test_failure_in_one_partition_does_not_block_another(
        self, handler: AsyncMock
    ):
        """
        GIVEN a batch with messages from two partitions
        AND the handler fails for the message of partition 0
        WHEN the batch is processed
        THEN partition 0 seeks back AND partition 1 is still processed and committed
        """
        handler.handle.side_effect = [RuntimeError("boom"), None]
        consumer = make_consumer({TP0: [message(0, PUT)], TP1: [message(9, PUT)]})
        manager = KafkaEventManager(consumer)
        manager.register_handler(PUT, handler)

        await run_until_cancelled(manager)

        consumer.seek.assert_called_once_with(TP0, 0)
        consumer.commit.assert_awaited_once_with({TP1: 10})

    async def test_empty_poll_commits_nothing(self, handler: AsyncMock):
        """
        GIVEN a poll that returns no messages
        WHEN the loop runs
        THEN nothing is committed and nothing is handled
        """
        consumer = make_consumer({})
        manager = KafkaEventManager(consumer)
        manager.register_handler(PUT, handler)

        await run_until_cancelled(manager)

        consumer.commit.assert_not_awaited()
        handler.handle.assert_not_awaited()
