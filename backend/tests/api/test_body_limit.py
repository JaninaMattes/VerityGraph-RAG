"""Tests for the request body size limit."""

from collections.abc import Iterator
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.api.middleware import BodySizeLimitMiddleware
from src.main import app as main_app
from src.main import settings

LIMIT = 10


class Recorder:
    """The bodies that reached the app."""

    def __init__(self) -> None:
        self.bodies: list[bytes] = []


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()


@pytest.fixture
def client(recorder: Recorder) -> TestClient:
    """A minimal app behind the limit; its route records the body it reads."""
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=LIMIT)

    @app.post("/echo")
    async def echo(request: Request) -> dict[str, int]:
        body = await request.body()
        recorder.bodies.append(body)
        return {"size": len(body)}

    return TestClient(app)


def chunks(*parts: bytes) -> Iterator[bytes]:
    """A body without Content-Length: httpx sends it chunked."""
    yield from parts


def assert_too_large(response) -> None:
    assert response.status_code == 413
    assert response.json() == {
        "error": "request_too_large",
        "message": "The request body is too large.",
    }


class TestBodySizeLimit:
    """Bodies up to the limit reach the app unchanged; larger ones get 413."""

    def test_body_at_the_limit_reaches_the_app(self, client, recorder):
        """
        GIVEN a body of exactly the limit
        WHEN it is posted
        THEN the app reads the whole body
        """
        response = client.post("/echo", content=b"x" * LIMIT)

        assert response.json() == {"size": LIMIT}
        assert recorder.bodies == [b"x" * LIMIT]

    def test_declared_length_over_the_limit_is_refused(self, client, recorder):
        """
        GIVEN a Content-Length one byte over the limit
        WHEN the body is posted
        THEN the response is 413 AND the app is not called
        """
        response = client.post("/echo", content=b"x" * (LIMIT + 1))

        assert_too_large(response)
        assert recorder.bodies == []

    def test_chunked_body_over_the_limit_is_refused(self, client, recorder):
        """
        GIVEN a chunked body without Content-Length that grows over the limit
        WHEN it is posted
        THEN the response is 413 AND the app is not called
        """
        response = client.post("/echo", content=chunks(b"x" * 6, b"x" * 6))

        assert_too_large(response)
        assert recorder.bodies == []

    def test_chunked_body_under_the_limit_reaches_the_app_whole(self, client, recorder):
        """
        GIVEN a chunked body of three parts, together under the limit
        WHEN it is posted
        THEN the app reads the parts joined in order
        """
        response = client.post("/echo", content=chunks(b"ab", b"cd", b"ef"))

        assert response.json() == {"size": 6}
        assert recorder.bodies == [b"abcdef"]

    async def test_other_protocols_pass_through(self):
        """
        GIVEN a lifespan (non-HTTP) message
        WHEN it reaches the middleware
        THEN it is passed to the app unchanged
        """
        app = AsyncMock()
        scope, receive, send = {"type": "lifespan"}, AsyncMock(), AsyncMock()

        await BodySizeLimitMiddleware(app, max_bytes=LIMIT)(scope, receive, send)

        app.assert_awaited_once_with(scope, receive, send)

    async def test_disconnect_while_reading_reaches_the_app(self):
        """
        GIVEN a client that disconnects before it sends a body
        WHEN the app reads the body and then waits for more messages
        THEN it first gets an empty body
        AND then the disconnect, so it can stop its work
        """
        disconnect = {"type": "http.disconnect"}
        receive = AsyncMock(return_value=disconnect)
        received: list[dict] = []

        async def app(scope, app_receive, send) -> None:
            received.extend([await app_receive(), await app_receive()])

        await BodySizeLimitMiddleware(app, max_bytes=LIMIT)(
            {"type": "http", "headers": []}, receive, AsyncMock()
        )

        assert received == [
            {"type": "http.request", "body": b"", "more_body": False},
            disconnect,
        ]

    def test_non_positive_limit_is_rejected(self):
        """
        GIVEN a limit of 0 bytes
        WHEN the middleware is created
        THEN ValueError is raised
        """
        with pytest.raises(ValueError):
            BodySizeLimitMiddleware(AsyncMock(), max_bytes=0)


class TestApplicationLimit:
    """The API applies the configured limit to every route."""

    def test_api_refuses_a_body_over_the_configured_limit(self):
        """
        GIVEN a login form one byte over MAX_REQUEST_BODY_BYTES
        WHEN it is posted to the API
        THEN the response is 413 with a request id, before any route code runs
        """
        limit = settings.max_request_body_bytes

        response = TestClient(main_app).post(
            "/api/v1/auth/token", content=b"x" * (limit + 1)
        )

        assert_too_large(response)
        assert response.headers["X-Request-ID"]
