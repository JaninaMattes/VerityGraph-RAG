"""Application exception hierarchy.

ApplicationException
├── AuthenticationException      no, invalid or expired credentials
├── PermissionDeniedException    the caller lacks the role for the operation
├── NotFoundException            the resource does not exist (or belongs to another tenant)
├── ConflictException            the write conflicts with existing data (duplicate key)
├── DatabaseException            the database failed; a retry may succeed
├── StorageException             object storage failed; a retry may succeed
│   └── StorageAccessDeniedException  the storage credentials are wrong; a retry cannot help
└── DocumentParsingException     the file is corrupt or has an unsupported format

The API maps each family to one HTTP response (exception_handlers.py). The Temporal
activities map them to retryable or non-retryable errors. `message` is for logs only;
it is never sent to clients.
"""


class ApplicationException(Exception):
    """Base class for all expected errors of the application."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundException(ApplicationException):
    """A requested resource does not exist. Subclasses set `resource`."""

    resource = "Resource"

    def __init__(self, identifier: object) -> None:
        super().__init__(f"{self.resource} '{identifier}' was not found.")
        self.identifier = identifier


class DocumentNotFoundException(NotFoundException):
    resource = "Document"


class IngestionJobNotFoundException(NotFoundException):
    resource = "Ingestion job"


class TenantNotFoundException(NotFoundException):
    resource = "Tenant"


class UserNotFoundException(NotFoundException):
    resource = "User"


class BucketNotFoundException(NotFoundException):
    resource = "Bucket"


class ObjectNotFoundException(NotFoundException):
    """A storage object does not exist. The identifier is '<bucket>/<key>'."""

    resource = "Object"


class AuthenticationException(ApplicationException):
    """The caller has no valid credentials: no token, a bad token or a bad password."""


class PermissionDeniedException(ApplicationException):
    """The caller is authenticated but lacks the role for the operation."""


class ConflictException(ApplicationException):
    """A write conflicts with existing data, for example a duplicate key."""


class DatabaseException(ApplicationException):
    """The database failed (connection, timeout, query error)."""


class StorageException(ApplicationException):
    """The object storage failed (network, timeout, server error)."""


class StorageAccessDeniedException(StorageException):
    """The storage rejected the credentials or permissions of the application."""


class DocumentParsingException(ApplicationException):
    """The parser cannot read the file (corrupt or unsupported). A retry cannot help."""
