"""Map exceptions to HTTP responses with one error envelope.

Every error response has the body {"error": <code>, "message": <public text>}; a
validation error also has "details". The internal exception message is never sent to
the client. Client errors (4xx) are logged as warnings with the reason; server errors
(5xx) are logged with the full traceback.
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.libs.core.logger import get_logger
from src.libs.exceptions.exceptions import (
    ConflictException,
    DatabaseException,
    NotFoundException,
    StorageException,
)

logger = get_logger(__name__)

# exception type -> (status code, error code, public message)
ERROR_RESPONSES: dict[type[Exception], tuple[int, str, str]] = {
    NotFoundException: (404, "not_found", "The requested resource couldn't be found."),
    ConflictException: (409, "conflict", "The entry exists already."),
    DatabaseException: (500, "database_error", "Database operation failed."),
    StorageException: (503, "storage_error", "The file storage is not available."),
    Exception: (500, "internal_server_error", "An unexpected error occurred."),
}


def _make_handler(
    status_code: int, error: str, message: str
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        if status_code >= 500:
            logger.exception("request error", error=error)
        else:
            logger.warning("request rejected", error=error, reason=str(exc))
        return JSONResponse(
            status_code=status_code, content={"error": error, "message": message}
        )

    return handler


async def _validation_handler(request: Request, exc: Exception) -> JSONResponse:
    details = exc.errors() if isinstance(exc, RequestValidationError) else []
    logger.warning("request rejected", error="validation_error")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "error": "validation_error",
            "message": "The request is invalid.",
            "details": jsonable_encoder(details),
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register one handler per ERROR_RESPONSES entry and the validation handler.

    Starlette picks the handler of the most specific class, so for example
    StorageAccessDeniedException uses the StorageException entry.
    """
    for exc_type, (status_code, error, message) in ERROR_RESPONSES.items():
        app.add_exception_handler(exc_type, _make_handler(status_code, error, message))
    app.add_exception_handler(RequestValidationError, _validation_handler)
