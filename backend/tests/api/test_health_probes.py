"""Tests for the liveness and readiness endpoints (used by Compose and Render)."""

import asyncio
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from src.api.dependencies import get_readiness_probes
from src.api.routers import health
from src.libs.exceptions.exceptions import BucketNotFoundException
from src.main import app


async def ok() -> None:
    """A probe that succeeds."""


async def broken() -> None:
    """A probe that fails like an unreachable database."""
    raise ConnectionRefusedError("connection refused")


async def hanging() -> None:
    """A probe that never answers."""
    await asyncio.sleep(10)


@pytest.fixture
def probes() -> Iterator[dict]:
    """Replace the real probes with the dictionary that the test fills."""
    selected: dict = {}
    app.dependency_overrides[get_readiness_probes] = lambda: selected
    yield selected
    app.dependency_overrides.pop(get_readiness_probes, None)


class TestLiveness:
    """The liveness probe needs no dependency."""

    async def test_live_returns_ok(self, client: AsyncClient):
        """
        GIVEN the API process runs
        WHEN GET /health/live is called
        THEN the response is 200 with status 'ok'
        """
        response = await client.get("/api/v1/health/live")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestReadiness:
    """The readiness probe reports each dependency and fails if one fails."""

    async def test_all_probes_pass(self, client: AsyncClient, probes: dict):
        """
        GIVEN the database and the storage answer
        WHEN GET /health/ready is called
        THEN the response is 200 and every check is 'ok'
        """
        probes.update(database=ok, storage=ok)

        response = await client.get("/api/v1/health/ready")

        assert response.status_code == 200
        assert response.json() == {
            "status": "ready",
            "checks": {"database": "ok", "storage": "ok"},
        }

    async def test_failed_probe_returns_503(self, client: AsyncClient, probes: dict):
        """
        GIVEN the database is unreachable and the storage answers
        WHEN GET /health/ready is called
        THEN the response is 503 AND only the database check is 'failed'
        """
        probes.update(database=broken, storage=ok)

        response = await client.get("/api/v1/health/ready")

        assert response.status_code == 503
        assert response.json() == {
            "status": "not_ready",
            "checks": {"database": "failed", "storage": "ok"},
        }

    async def test_slow_probe_times_out(
        self, client: AsyncClient, probes: dict, monkeypatch: pytest.MonkeyPatch
    ):
        """
        GIVEN a probe that does not answer within the timeout
        WHEN GET /health/ready is called
        THEN the response is 503 without waiting for the probe
        """
        monkeypatch.setattr(health, "PROBE_TIMEOUT_SECONDS", 0.01)
        probes.update(storage=hanging)

        response = await client.get("/api/v1/health/ready")

        assert response.status_code == 503
        assert response.json()["checks"] == {"storage": "failed"}


class TestReadinessProbes:
    """The real probes query the database engine and the storage bucket."""

    async def test_database_probe_runs_a_query(self):
        """
        GIVEN an engine whose connection accepts queries
        WHEN the database probe runs
        THEN it executes one query on a new connection
        """
        connection = AsyncMock()
        engine = MagicMock()
        engine.connect.return_value.__aenter__.return_value = connection
        request = MagicMock()
        request.app.state.db_engine = engine

        await get_readiness_probes(request, MagicMock())["database"]()

        connection.execute.assert_awaited_once()

    async def test_storage_probe_checks_the_bucket(self):
        """
        GIVEN a storage whose bucket check fails
        WHEN the storage probe runs
        THEN the storage error reaches the caller
        """
        storage = MagicMock()
        storage.check_available.side_effect = BucketNotFoundException("documents")

        with pytest.raises(BucketNotFoundException):
            await get_readiness_probes(MagicMock(), storage)["storage"]()
