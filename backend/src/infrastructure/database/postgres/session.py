# src/infrastructure/database/postgres/session.py

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.libs.core.logger import get_logger

logger = get_logger("api.infrastructure.postgres")

# Create an async session factory
def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,  # Important for async
        autocommit=False,
        autoflush=False,
    )


# FastAPI Dependency
async def get_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Utilise generator as context manager.
    Yields a database session and ensures proper cleanup.
    """
    factory = request.app.state.session_factory
    async with factory() as session:
        try:
            yield session  # suspends execution and passes session to 'with' block
        except Exception:
            logger.warning("Request failed, rolling back database session.")
            await session.rollback()
            raise
        finally:
            logger.info("Database session closed.")
            await session.close()