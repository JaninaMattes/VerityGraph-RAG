from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.logger import get_logger
from src.infrastructure.database.postgres.engine import async_engine

logger = get_logger("api-backend.infrastructure.postgres")

# Create a session factory
async_session_factory = async_sessionmaker(
    bind=async_engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Utilise generator as context manager."""
    async with async_session_factory() as session:
        try:
            yield session  # suspends execution and passes session to 'with' block
        except Exception:
            logger.exception("Session generation failure! Session is rolled back.")
            await session.rollback()
            raise
        finally:
            await session.close()
