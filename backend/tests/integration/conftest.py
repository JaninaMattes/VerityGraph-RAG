"""Fixtures for tests against a real, disposable PostgreSQL database.

Set TEST_DATABASE_URL (for example postgresql+asyncpg://postgres@localhost:5432/test)
to run them; otherwise every test in this folder is skipped. The database is
migrated to the newest revision once and emptied after each test.
"""

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from alembic import command
from src.libs.core.config import get_settings

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


@pytest.fixture(scope="session")
def alembic_config() -> Iterator[Config]:
    """An Alembic config whose env.py connects to the test database."""
    previous = os.environ.get("POSTGRES_URL")
    os.environ["POSTGRES_URL"] = TEST_DATABASE_URL or ""
    get_settings.cache_clear()
    yield Config(str(ALEMBIC_INI))
    if previous is None:
        os.environ.pop("POSTGRES_URL", None)
    else:
        os.environ["POSTGRES_URL"] = previous
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def migrated(alembic_config: Config) -> Config:
    """Migrate the test database to the newest revision (once per session)."""
    command.upgrade(alembic_config, "head")
    return alembic_config


@pytest_asyncio.fixture
async def session(migrated: Config) -> AsyncIterator[AsyncSession]:
    """A session on the migrated database. All rows are deleted afterwards."""
    engine = create_async_engine(TEST_DATABASE_URL or "")
    async with AsyncSession(engine, expire_on_commit=False) as db_session:
        yield db_session
    async with engine.begin() as connection:
        await connection.execute(text("TRUNCATE tenant, pipeline_config CASCADE"))
    await engine.dispose()
