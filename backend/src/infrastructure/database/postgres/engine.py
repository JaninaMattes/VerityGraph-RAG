from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    create_async_engine,
)

from src.core.config import get_settings

settings = get_settings()

# Initialize the async DB engine
async_engine: AsyncEngine = create_async_engine(settings.database_url)
