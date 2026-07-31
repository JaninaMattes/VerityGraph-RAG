from fastapi import FastAPI, Request
from fastapi.concurrency import asynccontextmanager
from fastapi.responses import JSONResponse

from src.api.routers import document, health, hello_world, tenant, user
from src.core.config import get_settings
from src.core.logger import get_logger, setup_logging
from src.infrastructure.database.postgres.engine import async_engine
from src.utils.exceptions import (
    DocumentNotFoundException,
    TenantNotFoundException,
    UserNotFoundException,
)

# Initialization before FastAPI constructed
setup_logging(log_level="INFO")
logger = get_logger("api.main")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    yield
    # Shutdown
    await async_engine.dispose()


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)


# Exception handler
@app.exception_handler(TenantNotFoundException)
async def tenant_exception_handler(request: Request, exc: TenantNotFoundException):
    return JSONResponse(
        status_code=418,
        content={"message": f"{exc.name}: {exc.message}"},
    )


@app.exception_handler(UserNotFoundException)
async def user_exception_handler(request: Request, exc: UserNotFoundException):
    return JSONResponse(
        status_code=418,
        content={"message": f"{exc.name}: {exc.message}"},
    )


@app.exception_handler(DocumentNotFoundException)
async def document_exception_handler(request: Request, exc: DocumentNotFoundException):
    return JSONResponse(
        status_code=418,
        content={"message": f"{exc.name}: {exc.message}"},
    )


app.include_router(hello_world.router, prefix=settings.api_prefix, tags=["Hello-World"])
app.include_router(health.router, prefix=settings.api_prefix, tags=["Health"])
app.include_router(tenant.router, prefix=settings.api_prefix, tags=["Tenants"])
app.include_router(user.router, prefix=settings.api_prefix, tags=["Users"])
app.include_router(document.router, prefix=settings.api_prefix, tags=["Documents"])