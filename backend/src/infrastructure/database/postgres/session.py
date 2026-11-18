"""Session factory and the per-request unit of work."""

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.libs.core.logger import get_logger

logger = get_logger("api.infrastructure.postgres")


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create the session factory. Loaded attributes stay readable after commit."""
    return async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession]:
    """Yield one session per request: commit on success, roll back on any error.

    Use it with Depends(..., scope="function") so that the commit runs before the
    response is sent and a failed commit reaches the client as an error.
    """
    async with request.app.state.session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            logger.warning("Request failed, rolling back the database session.")
            await session.rollback()
            raise
