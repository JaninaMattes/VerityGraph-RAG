from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.infrastructure.database.postgres.engine import async_engine
from src.utils.logger import get_logger

logger = get_logger("api-backend.infrastructure.postgres")

# Create a session factory
async_session_factory = async_sessionmaker(bind=async_engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Utilise generator as context manager."""
    async with async_session_factory() as session:
        try:
            yield session  # suspends execution and passes session to 'with' block
        except Exception as e:
            logger.error(f"Session generation failure! Error: {e}", exc_info=True)
            await session.rollback()
            raise
        finally:
            await session.close()
