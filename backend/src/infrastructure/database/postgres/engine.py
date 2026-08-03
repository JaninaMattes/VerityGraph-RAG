from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)

from src.shared.core.config import get_settings

settings = get_settings()

# Web application: Initialize the async DB engine
async_engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    future=True,  # Use SQLAlchemy 2.0 behaviors
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_size=20,  # Connection pool size
)
