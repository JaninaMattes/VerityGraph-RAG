"""Fixtures that run Postgres and MinIO in throw-away Docker containers.

Opt-in with E2E=1 (`make test-e2e`); the tests are skipped without it or without
Docker. Each container gets a free local port and credentials made for this run,
and is removed after the session, also when a test fails.
"""

import secrets
import subprocess
import time
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.config import Config
from minio import Minio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from alembic import command
from src.libs.core.config import get_settings

# The images of docker/compose.yaml, so the test runs what the stack runs.
POSTGRES_IMAGE = "postgres:16-alpine"
MINIO_IMAGE = "pgsty/minio:RELEASE.2026-08-04T00-00-00Z"
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
READY_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class MinioServer:
    endpoint: str
    access_key: str
    secret_key: str

    def client(self) -> Minio:
        return Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=False,
        )


def docker(*args: str) -> str:
    """Run a docker command and return its output. Raise if it fails."""
    return subprocess.run(
        ["docker", *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def is_ready(ready: Callable[[], bool]) -> bool:
    """Return the result of `ready`, or False if it raises (the server is starting)."""
    try:
        return ready()
    except Exception:  # noqa: BLE001
        return False


def wait_until(ready: Callable[[], bool], what: str) -> None:
    """Call `ready` until it returns True. Fail the test after the timeout."""
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if is_ready(ready):
            return
        time.sleep(0.5)
    pytest.fail(f"{what} was not ready after {READY_TIMEOUT_SECONDS} s.")


@pytest.fixture(scope="session")
def container() -> Iterator[Callable[..., tuple[str, str]]]:
    """Start containers on free local ports; remove them all after the session.

    The returned function takes the image, the container port, the environment
    and the command, and returns (container id, "127.0.0.1:<host port>").
    """
    started: list[str] = []

    def start(
        image: str, port: int, env: dict[str, str], *command: str
    ) -> tuple[str, str]:
        env_args = [arg for k, v in env.items() for arg in ("-e", f"{k}={v}")]
        container_id = docker(
            "run", "-d", "--rm", "-p", f"127.0.0.1::{port}", *env_args, image, *command
        )
        started.append(container_id)
        address = docker("port", container_id, f"{port}/tcp").splitlines()[0]
        return container_id, address

    yield start
    for container_id in started:
        subprocess.run(
            ["docker", "rm", "-f", container_id], check=False, capture_output=True
        )


@pytest.fixture(scope="session")
def database_url(container: Callable[..., tuple[str, str]]) -> Iterator[str]:
    """A Postgres container migrated to the newest revision."""
    container_id, address = container(
        POSTGRES_IMAGE,
        5432,
        {"POSTGRES_HOST_AUTH_METHOD": "trust", "POSTGRES_DB": "e2e"},
    )
    # The init server does not listen on TCP, so this passes only for the real one.
    wait_until(
        lambda: (
            subprocess.run(
                ["docker", "exec", container_id, "pg_isready", "-h", "127.0.0.1"],
                check=False,
                capture_output=True,
            ).returncode
            == 0
        ),
        "Postgres",
    )
    url = f"postgresql+asyncpg://postgres@{address}/e2e"
    with pytest.MonkeyPatch.context() as env:
        env.setenv("POSTGRES_URL", url)  # alembic/env.py reads the settings
        get_settings.cache_clear()
        command.upgrade(Config(str(ALEMBIC_INI)), "head")
    get_settings.cache_clear()
    yield url


@pytest.fixture(scope="session")
def minio_server(container: Callable[..., tuple[str, str]]) -> MinioServer:
    """A MinIO container with credentials made for this run."""
    access_key, secret_key = "e2e", secrets.token_hex(16)
    _, address = container(
        MINIO_IMAGE,
        9000,
        {"MINIO_ROOT_USER": access_key, "MINIO_ROOT_PASSWORD": secret_key},
        "server",
        "/data",
    )
    server = MinioServer(address, access_key, secret_key)
    client = server.client()
    wait_until(lambda: client.list_buckets() is not None, "MinIO")
    return server


@pytest_asyncio.fixture
async def db_engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(database_url)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)
