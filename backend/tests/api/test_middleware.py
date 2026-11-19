"""Tests for the request context middleware (request id and access log)."""

import json
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from src.libs.core.logger import setup_logging


def make_client() -> TestClient:
    """A minimal app with the middleware. Call it inside the test body, so that
    the JSON log handler writes to the stdout that capsys captures."""
    setup_logging("INFO", json_logs=True)
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/items")
    async def items() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/fail")
    async def fail() -> None:
        raise RuntimeError("boom")

    return TestClient(app, raise_server_exceptions=False)


def access_lines(output: str) -> list[dict[str, Any]]:
    lines = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
    return [line for line in lines if line.get("logger") == "src.api.middleware"]


class TestRequestId:
    """Every response carries a request id that the logs also contain."""

    def test_missing_header_generates_id(self):
        """
        GIVEN a request without X-Request-ID
        WHEN it is handled
        THEN the response carries a new 32-character request id
        """
        response = make_client().get("/items")

        assert response.status_code == 200
        assert len(response.headers[REQUEST_ID_HEADER]) == 32

    def test_valid_header_is_reused(self):
        """
        GIVEN a request with a valid X-Request-ID (for example from a gateway)
        WHEN it is handled
        THEN the response carries the same id
        """
        response = make_client().get(
            "/items", headers={REQUEST_ID_HEADER: "gw-123.a_b"}
        )

        assert response.headers[REQUEST_ID_HEADER] == "gw-123.a_b"

    @pytest.mark.parametrize(
        "header",
        ["bad id with spaces", "x" * 65, "line\\nbreak"],
        ids=["spaces", "long", "escape"],
    )
    def test_unsafe_header_is_replaced(self, header):
        """
        GIVEN a request id with unsafe characters or more than 64 characters
        WHEN it is handled
        THEN a new id replaces it, so clients cannot inject text into the logs
        """
        response = make_client().get("/items", headers={REQUEST_ID_HEADER: header})

        assert response.headers[REQUEST_ID_HEADER] != header
        assert len(response.headers[REQUEST_ID_HEADER]) == 32


class TestAccessLog:
    """One access line per request, with the request context."""

    def test_completed_request_is_logged_with_context(self, capsys):
        """
        GIVEN a successful request
        WHEN it is handled
        THEN one 'request completed' line holds id, method, path, status and duration
        """
        response = make_client().get("/items")

        (line,) = access_lines(capsys.readouterr().out)
        assert line["event"] == "request completed"
        assert line["request_id"] == response.headers[REQUEST_ID_HEADER]
        assert (line["method"], line["path"], line["status_code"]) == (
            "GET",
            "/items",
            200,
        )
        assert line["duration_ms"] >= 0

    def test_failed_request_is_logged(self, capsys):
        """
        GIVEN a route that raises an unexpected error
        WHEN it is handled
        THEN the response is 500 AND a 'request failed' line is written
        """
        response = make_client().get("/fail")

        assert response.status_code == 500
        (line,) = access_lines(capsys.readouterr().out)
        assert line["event"] == "request failed"
        assert line["path"] == "/fail"

    def test_context_does_not_leak_between_requests(self, capsys):
        """
        GIVEN two requests on the same client
        WHEN both are handled
        THEN each access line carries its own request id
        """
        client = make_client()
        first = client.get("/items").headers[REQUEST_ID_HEADER]
        second = client.get("/items").headers[REQUEST_ID_HEADER]

        ids = [line["request_id"] for line in access_lines(capsys.readouterr().out)]
        assert ids == [first, second]
        assert first != second
