"""FastAPI application: settings, logging, middleware, error handlers and routers.

Run it with `uvicorn src.main:app`. The database engine is created at startup and
disposed at shutdown (lifespan).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from src.api.routers import auth, document, health, tenant, user
from src.infrastructure.database.postgres.engine import create_async_db_engine
from src.infrastructure.database.postgres.session import create_session_factory
from src.infrastructure.storage.client import create_storage_client
from src.libs.core.config import get_settings
from src.libs.core.logger import get_logger, setup_logging
from src.libs.exceptions.exception_handlers import register_exception_handlers

settings = get_settings()
setup_logging(settings.log_level, json_logs=settings.log_json)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create the shared clients before the first request; release them at shutdown.

    One MinIO client per process reuses its connection pool for every request.
    """
    app.state.db_engine = create_async_db_engine(settings)
    app.state.session_factory = create_session_factory(app.state.db_engine)
    app.state.storage_client = create_storage_client(settings)
    logger.info("API started", environment=settings.environment)
    yield
    await app.state.db_engine.dispose()
    logger.info("API stopped")


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Starlette runs the middleware added last first: CORS wraps the request context.
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(settings.frontend_url).rstrip("/")],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[REQUEST_ID_HEADER],
)
register_exception_handlers(app)

for router, tag in (
    (health.router, "Health"),
    (auth.router, "Authentication"),
    (tenant.router, "Tenants"),
    (user.router, "Users"),
    (document.router, "Documents"),
):
    app.include_router(router, prefix=settings.api_prefix, tags=[tag])
