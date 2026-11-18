# src/infrastructure/database/postgres/engine.py

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)

from src.libs.core.config import Settings


def create_async_db_engine(settings: Settings) -> AsyncEngine:
    """Create the async engine. It connects lazily, on the first query."""
    return create_async_engine(
        url=settings.postgres_url.unicode_string(),
        echo=settings.postgres_echo,
        pool_recycle=3600,  # Recycle connections after 1 hour
        pool_size=settings.postgres_pool_size,
    )
