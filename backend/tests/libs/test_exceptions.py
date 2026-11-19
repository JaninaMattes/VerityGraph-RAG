"""Tests for the application exception hierarchy."""

import uuid

import pytest
from src.libs.exceptions.exceptions import (
    ApplicationException,
    BucketNotFoundException,
    ConflictException,
    DatabaseException,
    DocumentNotFoundException,
    DocumentParsingException,
    IngestionJobNotFoundException,
    NotFoundException,
    ObjectNotFoundException,
    StorageAccessDeniedException,
    StorageException,
    TenantNotFoundException,
    UserNotFoundException,
)


class TestNotFoundExceptions:
    """Every not-found error names its resource and keeps the requested identifier."""

    @pytest.mark.parametrize(
        ("exc_cls", "resource"),
        [
            (DocumentNotFoundException, "Document"),
            (IngestionJobNotFoundException, "Ingestion job"),
            (TenantNotFoundException, "Tenant"),
            (UserNotFoundException, "User"),
            (BucketNotFoundException, "Bucket"),
            (ObjectNotFoundException, "Object"),
        ],
    )
    def test_message_names_resource_and_identifier(self, exc_cls, resource):
        """
        GIVEN an identifier that does not exist
        WHEN the resource-specific not-found error is raised
        THEN it is a NotFoundException, keeps the identifier
        AND the message names the resource and the identifier
        """
        identifier = uuid.uuid4()

        exc = exc_cls(identifier)

        assert isinstance(exc, NotFoundException)
        assert exc.identifier == identifier
        assert exc.message == f"{resource} '{identifier}' was not found."
        assert str(exc) == exc.message


class TestHierarchy:
    """All expected errors share one base class; families do not overlap."""

    @pytest.mark.parametrize(
        "exc",
        [
            NotFoundException("x"),
            ConflictException("duplicate"),
            DatabaseException("down"),
            StorageException("down"),
            StorageAccessDeniedException("denied"),
            DocumentParsingException("corrupt file"),
        ],
        ids=[
            "not-found",
            "conflict",
            "database",
            "storage",
            "storage-access-denied",
            "parsing",
        ],
    )
    def test_every_error_is_an_application_exception(self, exc):
        """
        GIVEN any expected error
        WHEN its type is checked
        THEN it is an ApplicationException with a message
        """
        assert isinstance(exc, ApplicationException)
        assert exc.message

    def test_access_denied_is_a_storage_error(self):
        """
        GIVEN a storage access-denied error
        WHEN its family is checked
        THEN it is a StorageException and not a NotFoundException
        """
        exc = StorageAccessDeniedException("denied")

        assert isinstance(exc, StorageException)
        assert not isinstance(exc, NotFoundException)

    def test_conflict_is_not_a_database_failure(self):
        """
        GIVEN a conflict (a client error)
        WHEN its family is checked
        THEN it is not a DatabaseException (a server error)
        """
        assert not isinstance(ConflictException("duplicate"), DatabaseException)
