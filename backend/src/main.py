from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routers import document, health, tenant, user
from src.infrastructure.database.postgres.engine import (
    create_async_db_engine,
)
from src.infrastructure.database.postgres.session import create_session_factory
from src.libs.core.config import get_settings
from src.libs.core.logger import get_logger, setup_logging
from src.libs.exceptions.exception_handlers import register_exception_handlers

# Load lightweight settings at module level
settings = get_settings()

# Initialization before FastAPI constructed
setup_logging(log_level=settings.log_level)
logger = get_logger("api.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Startup phase
    # Create resources before serving requests and attach them to app.state
    logger.info("Initializing database engine...")
    app.state.db_engine = create_async_db_engine(settings)
    app.state.session_factory = create_session_factory(app.state.db_engine)
    logger.info("FastAPI startup complete.")

    # Yield control to FastAPI
    yield

    # 2. Shutdown phase
    # Clean up resources when Uvicorn sends SIGTERM signal
    logger.info("Shutting down FastAPI and disposing DB connections...")
    await app.state.db_engine.dispose()


# Initialize the app with the lifespan context manager
app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Register exception handlers and routers
register_exception_handlers(app)
app.include_router(health.router, prefix=settings.api_prefix, tags=["Health"])
app.include_router(tenant.router, prefix=settings.api_prefix, tags=["Tenants"])
app.include_router(user.router, prefix=settings.api_prefix, tags=["Users"])
app.include_router(document.router, prefix=settings.api_prefix, tags=["Documents"])