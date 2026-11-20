"""HTTP middleware: request id, one access log line per request, body size limit."""

import re
import time
import uuid

import structlog
from starlette.datastructures import Headers
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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


class BodySizeLimitMiddleware:
    """Refuse a request body larger than `max_bytes` with 413, before the app runs.

    A larger Content-Length is refused at once. Otherwise the body is read up to the
    limit and then given to the app, so a chunked body cannot grow without bound.
    File bytes go directly to object storage, so API bodies are small.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        if max_bytes < 1:
            raise ValueError("max_bytes must be positive.")
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = Headers(scope=scope).get("content-length", "")
        too_large = declared.isdigit() and int(declared) > self.max_bytes
        body = None if too_large else await self._read_body(receive)
        if body is None:
            await self._too_large(scope, receive, send)
            return

        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if replayed:
                return await receive()  # for example http.disconnect
            replayed = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay, send)

    async def _read_body(self, receive: Receive) -> bytes | None:
        """Return the whole body, or None as soon as it exceeds the limit."""
        parts: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                break  # the client disconnected; the app sees an empty body
            part = message.get("body", b"")
            size += len(part)
            if size > self.max_bytes:
                return None
            parts.append(part)
            if not message.get("more_body", False):
                break
        return b"".join(parts)

    @staticmethod
    async def _too_large(scope: Scope, receive: Receive, send: Send) -> None:
        logger.warning("request rejected", error="request_too_large")
        response = JSONResponse(
            status_code=413,
            content={
                "error": "request_too_large",
                "message": "The request body is too large.",
            },
        )
        await response(scope, receive, send)
