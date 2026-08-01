from fastapi import FastAPI, Request
from fastapi.concurrency import asynccontextmanager
from fastapi.responses import JSONResponse

from src.api.routers import document, health, hello_world, tenant, user
from src.core.config import get_settings
from src.core.logger import get_logger, setup_logging
from src.infrastructure.database.postgres.engine import async_engine
from src.utils.exceptions import (
    DatabaseException,
    DocumentServiceException,
    NotFoundException,
    StorageException,
    TenantNotFoundException,
    TenantServiceException,
    UserServiceException,
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
@app.exception_handler(DatabaseException)
async def database_exception_handler(
    request: Request,
    exc: DatabaseException,
) -> JSONResponse:
    logger.warning(
        "Database error during request %s %s",
        request.method,
        request.url,
    )
    return JSONResponse(
        status_code=400,
        content={
            "error": "database_error",
            "detail": exc.message,
        },
    )


@app.exception_handler(StorageException)
async def storage_exception_handler(request: Request, exc: StorageException):
    return JSONResponse(
        status_code=403,
        content={
            "error": "storage_error",
            "detail": exc.message,
        },
    )


@app.exception_handler(NotFoundException)
async def not_found_exception_handler(
    request: Request,
    exc: NotFoundException,
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": "not_found",
            "detail": exc.message,
        },
    )


@app.exception_handler(TenantServiceException)
async def tenant_service_exception_handler(
    request: Request,
    exc: TenantServiceException,
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "detail": exc.message,
        },
    )


@app.exception_handler(UserServiceException)
async def user_service_exception_handler(
    request: Request,
    exc: UserServiceException,
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "detail": exc.message,
        },
    )


@app.exception_handler(DocumentServiceException)
async def service_exception_handler(
    request: Request,
    exc: DocumentServiceException,
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "detail": exc.message,
        },
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(
    request: Request,
    exc: Exception,
):
    logger.exception(
        "Unhandled exception during request %s %s",
        request.method,
        request.url,
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred.",
        },
    )

# Router handling
app.include_router(hello_world.router, prefix=settings.api_prefix, tags=["Hello-World"])
app.include_router(health.router, prefix=settings.api_prefix, tags=["Health"])
app.include_router(tenant.router, prefix=settings.api_prefix, tags=["Tenants"])
app.include_router(user.router, prefix=settings.api_prefix, tags=["Users"])
app.include_router(document.router, prefix=settings.api_prefix, tags=["Documents"])