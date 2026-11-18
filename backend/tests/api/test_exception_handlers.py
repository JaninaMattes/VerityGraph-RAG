"""Tests for the mapping of application exceptions to HTTP responses."""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.libs.exceptions.exception_handlers import register_exception_handlers
from src.libs.exceptions.exceptions import (
    AccessDeniedException,
    BucketNotFoundException,
    DatabaseInternalException,
    DatabaseOperationException,
    DocumentNotFoundException,
    StorageOperationException,
)


def client_raising(exc: Exception) -> TestClient:
    """A minimal app whose only route raises the given exception."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/")
    async def fail() -> None:
        raise exc

    return TestClient(app, raise_server_exceptions=False)


class TestExceptionHandlers:
    """Each exception family has one status code and one error body."""

    @pytest.mark.parametrize(
        ("exc", "status_code", "error"),
        [
            (DatabaseOperationException("dup"), 400, "database_error"),
            (DatabaseInternalException("down"), 500, "database_error"),
            (StorageOperationException("files", "x"), 503, "storage_error"),
            (AccessDeniedException("files"), 403, "storage_error"),
            (DocumentNotFoundException(uuid.uuid4()), 404, "not_found"),
            (BucketNotFoundException("files"), 404, "not_found"),
            (RuntimeError("bug"), 500, "internal_server_error"),
        ],
        ids=[
            "db-conflict",
            "db-internal",
            "storage",
            "access-denied",
            "not-found",
            "not-found-subclass",
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
