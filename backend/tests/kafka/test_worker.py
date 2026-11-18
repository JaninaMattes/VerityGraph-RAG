"""Tests for the background worker composition root."""

import asyncio
import signal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from temporalio.contrib.pydantic import pydantic_data_converter

from src.infrastructure.message_broker.kafka import worker
from src.libs.core.config import Settings

pytestmark = pytest.mark.asyncio

MODULE = "src.infrastructure.message_broker.kafka.worker"


class TestCreateConsumer:
    """The consumer is configured from the settings with manual commits."""

    async def test_consumer_uses_settings_and_manual_commit(
        self, test_settings: Settings
    ):
        """
        GIVEN the application settings
        WHEN the consumer is created
        THEN it subscribes to the configured topics with the configured group
        AND auto commit is disabled, because the manager commits after success
        """
        with patch(f"{MODULE}.AIOKafkaConsumer") as consumer_cls:
            worker.create_consumer(test_settings)

        args, kwargs = consumer_cls.call_args
        assert args == tuple(test_settings.kafka_topics)
        assert kwargs["bootstrap_servers"] == test_settings.kafka_bootstrap_servers
        assert kwargs["group_id"] == test_settings.kafka_group_id
        assert kwargs["auto_offset_reset"] == test_settings.kafka_auto_offset_reset
        assert kwargs["enable_auto_commit"] is False


class TestSignalHandlers:
    """SIGTERM and SIGINT set the stop event."""

    async def test_handlers_are_registered_for_sigterm_and_sigint(self):
        """
        GIVEN a running event loop
        WHEN the signal handlers are installed
        THEN SIGTERM and SIGINT both call stop_event.set
        """
        stop_event = asyncio.Event()
        loop = MagicMock()

        with patch(f"{MODULE}.asyncio.get_running_loop", return_value=loop):
            worker.install_signal_handlers(stop_event)

        loop.add_signal_handler.assert_any_call(signal.SIGTERM, stop_event.set)
        loop.add_signal_handler.assert_any_call(signal.SIGINT, stop_event.set)

    async def test_unsupported_platform_is_tolerated(self):
        """
        GIVEN a platform without signal support (for example Windows)
        WHEN the signal handlers are installed
        THEN no error is raised
        """
        loop = MagicMock()
        loop.add_signal_handler.side_effect = NotImplementedError

        with patch(f"{MODULE}.asyncio.get_running_loop", return_value=loop):
            worker.install_signal_handlers(asyncio.Event())


class TestRunUntilStopped:
    """The worker runs the consumer until a stop signal or a consumer failure."""

    async def test_stop_event_cancels_consumer(self):
        """
        GIVEN a consumer that runs forever
        WHEN the stop event is set
        THEN run_until_stopped returns AND the consumer is cancelled
        """
        cancelled = asyncio.Event()

        async def consume_forever() -> None:
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        stop_event = asyncio.Event()
        stop_event.set()

        await worker.run_until_stopped(consume_forever(), stop_event)

        assert cancelled.is_set()

    async def test_consumer_failure_propagates(self):
        """
        GIVEN a consumer that fails
        WHEN run_until_stopped runs
        THEN the consumer error propagates, so the process exits and restarts
        """

        async def failing_consumer() -> None:
            raise RuntimeError("consumer crashed")

        with pytest.raises(RuntimeError, match="consumer crashed"):
            await worker.run_until_stopped(failing_consumer(), asyncio.Event())


class TestMain:
    """main() wires the infrastructure, the Temporal worker and the Kafka consumer."""

    async def test_main_composes_and_cleans_up(self, test_settings: Settings):
        """
        GIVEN all infrastructure factories are mocked
        AND the stop signal arrives at once
        WHEN main() runs
        THEN the Temporal worker serves the ingestion workflow and its activities
        AND the handler is registered for both 'ObjectCreated' event types
        AND the database engine is disposed
        """
        engine = MagicMock(dispose=AsyncMock())
        temporal_worker = MagicMock()
        temporal_worker.__aenter__ = AsyncMock(return_value=temporal_worker)
        temporal_worker.__aexit__ = AsyncMock(return_value=None)
        manager = MagicMock(run=AsyncMock())

        with (
            patch(f"{MODULE}.get_settings", return_value=test_settings),
            patch(f"{MODULE}.create_async_db_engine", return_value=engine),
            patch(f"{MODULE}.create_storage_client"),
            patch(f"{MODULE}.create_storage_service"),
            patch(f"{MODULE}.create_consumer"),
            patch(f"{MODULE}.Client.connect", new=AsyncMock()) as connect,
            patch(f"{MODULE}.Worker", return_value=temporal_worker) as worker_cls,
            patch(f"{MODULE}.KafkaEventManager", return_value=manager),
            patch(f"{MODULE}.install_signal_handlers", side_effect=lambda e: e.set()),
        ):
            await worker.main()

        assert connect.call_args.kwargs["data_converter"] is pydantic_data_converter
        kwargs = worker_cls.call_args.kwargs
        assert kwargs["task_queue"] == test_settings.temporal_task_queue
        assert kwargs["workflows"] == [worker.DocumentIngestionWorkflow]
        assert len(kwargs["activities"]) == 5
        registered = [call.args[0] for call in manager.register_handler.call_args_list]
        assert registered == list(worker.EVENT_TYPES)
        engine.dispose.assert_awaited_once()
