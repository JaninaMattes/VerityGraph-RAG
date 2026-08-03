from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager

from src.api.routers import document, health, hello_world, tenant, user
from src.infrastructure.database.postgres.engine import async_engine
from src.shared.core.config import get_settings
from src.shared.core.logger import get_logger, setup_logging
from src.shared.exception.exception_handlers import register_exception_handlers

# Initialization before FastAPI constructed
setup_logging(log_level="INFO")
logger = get_logger("api.main")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        # Startup
        yield
    except Exception:
        logger.exception("App engine generation failure!")
        raise
    finally:
        # Shutdown
        await async_engine.dispose()

settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Exception handling
register_exception_handlers(app)

# Router handling
app.include_router(hello_world.router, prefix=settings.api_prefix, tags=["Hello-World"])
app.include_router(health.router, prefix=settings.api_prefix, tags=["Health"])
app.include_router(tenant.router, prefix=settings.api_prefix, tags=["Tenants"])
app.include_router(user.router, prefix=settings.api_prefix, tags=["Users"])
app.include_router(document.router, prefix=settings.api_prefix, tags=["Documents"])