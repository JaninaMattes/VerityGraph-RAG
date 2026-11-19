"""HTTP middleware: request id and one access log line per request."""

import re
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.libs.core.logger import get_logger

logger = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
# Accept ids from a gateway only if they are short and safe to write into logs.
_SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind request id, method and path to every log record of a request.

    The id comes from a valid incoming X-Request-ID header, or is a new UUID. It is
    returned in the X-Request-ID response header, so a client can quote it in a
    support request. A response that an unhandled error produces carries no header.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER, "")
        if not _SAFE_REQUEST_ID.fullmatch(request_id):
            request_id = uuid.uuid4().hex

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id, method=request.method, path=request.url.path
        )
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.error("request failed", duration_ms=_elapsed_ms(started))
            raise

        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request completed",
            status_code=response.status_code,
            duration_ms=_elapsed_ms(started),
        )
        return response


def _elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)
