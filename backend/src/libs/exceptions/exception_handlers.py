"""Map application exceptions to HTTP responses.

Each exception family has one status code and one public error body. The body never
contains the internal exception message; the full error is logged instead.
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.libs.core.logger import get_logger
from src.libs.exceptions.exceptions import (
    AccessDeniedException,
    DatabaseInternalException,
    DatabaseOperationException,
    NotFoundException,
    StorageException,
)

logger = get_logger("api.exceptions")

# exception type -> (status code, error code, public message)
ERROR_RESPONSES: dict[type[Exception], tuple[int, str, str]] = {
    DatabaseOperationException: (
        400,
        "database_error",
        "The requested entry exists already.",
    ),
    DatabaseInternalException: (500, "database_error", "Database operation failed."),
    StorageException: (503, "storage_error", "A storage error occurred."),
    AccessDeniedException: (403, "storage_error", "Access to storage denied."),
    NotFoundException: (404, "not_found", "The requested resource couldn't be found."),
    Exception: (500, "internal_server_error", "An unexpected error occurred."),
}


def _make_handler(
    status_code: int, error: str, message: str
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Request %s %s failed with %s", request.method, request.url, error
        )
        return JSONResponse(
            status_code=status_code, content={"error": error, "message": message}
        )

    return handler


def register_exception_handlers(app: FastAPI) -> None:
    """Register one handler per entry of ERROR_RESPONSES.

    Starlette picks the handler of the most specific class, so AccessDeniedException
    wins over its base StorageException.
    """
    for exc_type, (status_code, error, message) in ERROR_RESPONSES.items():
        app.add_exception_handler(exc_type, _make_handler(status_code, error, message))
