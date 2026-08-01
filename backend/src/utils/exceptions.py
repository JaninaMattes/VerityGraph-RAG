"""
Application exception hierarchy.

Replace existing exceptions with the following structure.
"""


# ============================================================
# Base Application Exception
# ============================================================

from uuid import UUID


class ApplicationException(Exception):
    """
    Base exception for all expected application errors.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


# ============================================================
# Resource Not Found Exceptions
# ============================================================


class NotFoundException(ApplicationException):
    """
    Generic missing resource exception that manages all shared behaviour.
    """


class ObjectNotFoundException(NotFoundException):
    """
    Storage object does not exist.
    """

    def __init__(self, storage_key: str, bucket_name: str):
        super().__init__(
            f"Object '{storage_key}' does not exist in bucket '{bucket_name}'."
        )

        self.storage_key = storage_key
        self.bucket_name = bucket_name


class DocumentNotFoundException(NotFoundException):
    def __init__(self, document_id: UUID):
        super().__init__(f"Document with ID '{document_id}' was not found.")

        self.document_id = document_id


class UserNotFoundException(NotFoundException):
    def __init__(self, user_id: UUID):
        super().__init__(f"User with ID '{user_id}' was not found.")

        self.user_id = user_id


class TenantNotFoundException(NotFoundException):
    def __init__(self, tenant_id: UUID):
        super().__init__(f"Tenant with ID '{tenant_id}' was not found.")

        self.tenant_id = tenant_id


class CredentialsNotFoundException(NotFoundException):
    def __init__(self, credentials_id: UUID):
        super().__init__(f"Credentials with ID '{credentials_id}' was not found.")

        self.credentials_id = credentials_id


# ============================================================
# Document Exceptions
# ============================================================

class DomainException(ApplicationException):
    """Business rule violations."""


class DocumentNotReadyException(DomainException):
    """
    Document exists but cannot currently be processed.
    """


class DocumentNotCreatedException(ApplicationException):
    """
    Document exists but cannot currently be processed.
    """

    def __init__(self, document_id: UUID):
        super().__init__(f"Document with ID '{document_id}' was not created.")

        self.document_id = document_id


# ============================================================
# Database Exceptions
# ============================================================


class DatabaseException(ApplicationException):
    """
    Base database failure.

    Replaces:
        DatabaseError
    """


class DatabaseOperationException(DatabaseException):
    """
    General database operation failure.

    Replaces:
        DatabaseOperationError
    """


class DatabaseConnectionException(DatabaseException):
    """
    Database unavailable or connection failed.

    Replaces:
        DatabaseConnectionError
    """


class DatabaseTimeoutException(DatabaseException):
    """
    Database operation exceeded timeout.

    Replaces:
        DatabaseTimeoutError
    """


class EntityAlreadyExistsException(DatabaseException):
    """
    Duplicate entity creation.

    Replaces:
        EntityAlreadyExistsError
    """


# ============================================================
# Storage Exceptions
# ============================================================


class StorageException(ApplicationException):
    """
    Base object storage failure.
    """


class StorageOperationException(StorageException):
    """
    Storage provider operation failed.

    Replaces:
        StorageOperationError
    """

    def __init__(self, bucket_name: str, description: str):
        super().__init__(
            f"Storage operation failed for bucket '{bucket_name}'. {description}"
        )

        self.bucket_name = bucket_name


class AccessDeniedException(StorageException):
    """
    Action refused due to missing permissions or bad credentials.
    """

    def __init__(self, bucket_name: str):
        super().__init__(
            f"Access to bucket '{bucket_name}' refused due to missing permissions or bad credentials."
        )

        self.bucket_name = bucket_name


# ============================================================
# Service Layer Exceptions
# ============================================================


class ServiceException(ApplicationException):
    """
    Base exception for service layer failures.
    """

class AuthServiceException(ServiceException):
    """
    Document service failure.

    Replaces:
        DocumentServiceError
    """

class DocumentServiceException(ServiceException):
    """
    Document service failure.

    Replaces:
        DocumentServiceError
    """


class UserServiceException(ServiceException):
    """
    User service failure.

    Replaces:
        UserServiceError
    """


class TenantServiceException(ServiceException):
    """
    Tenant service failure.

    Replaces:
        TenantServiceError
    """
