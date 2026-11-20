"""Tests for the mapping of exceptions to HTTP responses and log records."""

import json
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from src.libs.core.logger import setup_logging
from src.libs.exceptions.exception_handlers import register_exception_handlers
from src.libs.exceptions.exceptions import (
    BucketNotFoundException,
    ConflictException,
    DatabaseException,
    DocumentNotFoundException,
    StorageAccessDeniedException,
    StorageException,
    TooManyRequestsException,
)


class Body(BaseModel):
    name: str


def client_raising(exc: Exception) -> TestClient:
    """A minimal app with one route that raises `exc` and one that validates a body.

    Call it inside the test body, so that the JSON log handler writes to the stdout
    that capsys captures.
    """
    setup_logging("INFO", json_logs=True)
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/")
    async def fail() -> None:
        raise exc

    @app.post("/items")
    async def create(body: Body) -> Body:
        return body

    return TestClient(app, raise_server_exceptions=False)


def handler_lines(output: str) -> list[dict]:
    lines = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
    return [
        line
        for line in lines
        if line.get("logger") == "src.libs.exceptions.exception_handlers"
    ]


class TestErrorResponses:
    """Each exception family has one status code and one public error body."""

    @pytest.mark.parametrize(
        ("exc", "status_code", "error"),
        [
            (DocumentNotFoundException(uuid.uuid4()), 404, "not_found"),
            (BucketNotFoundException("files"), 404, "not_found"),
            (ConflictException("duplicate key"), 409, "conflict"),
            (DatabaseException("connection lost"), 500, "database_error"),
            (StorageException("timeout"), 503, "storage_error"),
            (StorageAccessDeniedException("bad credentials"), 503, "storage_error"),
            (RuntimeError("bug"), 500, "internal_server_error"),
        ],
        ids=[
            "not-found",
            "not-found-subclass",
            "conflict",
            "database",
            "storage",
            "storage-access-denied",
            "unexpected",
        ],
    )
    def test_exception_is_mapped_to_response(self, exc, status_code, error):
        """
        GIVEN a route that raises an exception
        WHEN the route is called
        THEN the response has the mapped status code and error code
        AND the body never leaks the internal exception message
        """
        response = client_raising(exc).get("/")

        assert response.status_code == status_code
        body = response.json()
        assert body["error"] == error
        assert str(exc) not in body["message"]

    def test_too_many_requests_says_when_to_retry(self):
        """
        GIVEN a route that raises TooManyRequestsException with retry_after=40
        WHEN the route is called
        THEN the response is 429 'too_many_requests' with the header Retry-After: 40
        """
        response = client_raising(TooManyRequestsException(retry_after=40)).get("/")

        assert response.status_code == 429
        assert response.json()["error"] == "too_many_requests"
        assert response.headers["Retry-After"] == "40"

    def test_validation_error_uses_the_same_envelope(self):
        """
        GIVEN a request body without a required field
        WHEN the route is called
        THEN the response is 422 with error 'validation_error' and the field details
        """
        response = client_raising(RuntimeError()).post("/items", json={})

        assert response.status_code == 422
        body = response.json()
        assert body["error"] == "validation_error"
        assert body["details"][0]["loc"] == ["body", "name"]


class TestErrorLogging:
    """Client errors are warnings; server errors are logged with a traceback."""

    def test_client_error_is_a_warning_without_traceback(self, capsys):
        """
        GIVEN a route that raises a not-found error
        WHEN the route is called
        THEN one warning is logged with the reason and without a traceback
        """
        client_raising(DocumentNotFoundException("d1")).get("/")

        (line,) = handler_lines(capsys.readouterr().out)
        assert line["level"] == "warning"
        assert line["reason"] == "Document 'd1' was not found."
        assert "exception" not in line

    def test_server_error_is_logged_with_traceback(self, capsys):
        """
        GIVEN a route that raises a database error
        WHEN the route is called
        THEN one error is logged with the traceback
        """
        client_raising(DatabaseException("connection lost")).get("/")

        (line,) = handler_lines(capsys.readouterr().out)
        assert line["level"] == "error"
        assert "DatabaseException: connection lost" in line["exception"]
