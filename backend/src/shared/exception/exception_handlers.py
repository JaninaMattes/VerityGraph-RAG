from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.shared.core.logger import get_logger
from src.shared.exception.exceptions import (
    AccessDeniedException,
    DatabaseInternalException,
    DatabaseOperationException,
    NotFoundException,
    ServiceException,
    StorageException,
    StorageOperationException,
)

logger = get_logger("api.exceptions")


async def database_op_exception_handler(
    request: Request,
    exc: DatabaseOperationException,
) -> JSONResponse:
    logger.exception(
        "Database error during %s %s",
        request.method,
        request.url,
    )
    return JSONResponse(
        status_code=400,
        content={
            "error": "database_error",
            "message": "The requested entry exists already.",
        },
    )


async def database_int_exception_handler(
    request: Request,
    exc: DatabaseInternalException,
) -> JSONResponse:
    logger.exception(
        "Database error during %s %s",
        request.method,
        request.url,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "database_error",
            "message": "Database operation failed.",
        },
    )


async def storage_exception_handler(request: Request, exc: StorageOperationException):
    logger.exception(
        "Storage operations failure during %s %s",
        request.method,
        request.url,
    )
    return JSONResponse(
        status_code=503,
        content={
            "error": "storage_error",
            "message": "A storage error occured.",
        },
    )


async def access_denied_handler(request: Request, exc: AccessDeniedException):
    logger.exception(
        "Access denied to storage during %s %s",
        request.method,
        request.url,
    )
    return JSONResponse(
        status_code=403,
        content={
            "error": "storage_error",
            "message": "Access to storage denied.",
        },
    )


async def not_found_exception_handler(
    request: Request,
    exc: NotFoundException,
) -> JSONResponse:
    logger.exception(
        "Resource not found during %s %s",
        request.method,
        request.url,
    )
    return JSONResponse(
        status_code=404,
        content={
            "error": "not_found",
            "message": "The requested resource couldn't be found.",
        },
    )


async def service_exception_handler(
    request: Request,
    exc: ServiceException,
) -> JSONResponse:
    logger.exception(
        "Service failure during %s %s",
        request.method,
        request.url,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "A service error occured.",
        },
    )


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


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all application exception handlers.
    """
    app.add_exception_handler(
        DatabaseOperationException,
        database_op_exception_handler,  # type: ignore
    )

    app.add_exception_handler(
        DatabaseInternalException,
        database_int_exception_handler,  # type: ignore
    )

    app.add_exception_handler(
        StorageException,
        storage_exception_handler,  # type: ignore
    )

    app.add_exception_handler(
        AccessDeniedException,
        access_denied_handler,  # type: ignore
    )

    app.add_exception_handler(
        NotFoundException,
        not_found_exception_handler,  # type: ignore
    )

    app.add_exception_handler(
        ServiceException,
        service_exception_handler,  # type: ignore
    )

    app.add_exception_handler(
        Exception,
        unexpected_exception_handler,
    )
