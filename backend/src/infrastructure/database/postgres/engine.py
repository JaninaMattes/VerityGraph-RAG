# src/infrastructure/database/postgres/engine.py


from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)

from src.libs.core.config import Settings


def create_async_db_engine(settings: Settings) -> AsyncEngine:
    """Initialize the async DB engine"""
    return create_async_engine(
        url=str(settings.postgres_url.unicode_string()),
        echo=settings.postgres_echo,
        future=True,  # Use SQLAlchemy 2.0 behaviors
        pool_recycle=3600,  # Recycle connections after 1 hour
        pool_size=20,  # Connection pool size
    )
