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
# Authorisation Missing Exceptions
# ============================================================
class NoAuthorisationException(ApplicationException):
    """
    Generic missing resource exception that manages all shared behaviour.
    """

    def __init__(self, message: str):
        super().__init__("Unauthorised access!")
        self.message = message


class ResourceAccessDeniedException(NoAuthorisationException):
    """
    Generic missing resource exception that manages all shared behaviour.
    """

    def __init__(self, object_id: UUID, resource_name: str):
        super().__init__(
            f"Resource access denied for '{resource_name}' with '{object_id}'."
        )

        self.object_id = object_id
        self.resource_name = resource_name


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

class DocumentChunkNotFoundException(NotFoundException):
    def __init__(self, chunk_id: UUID, chunk_idx: int, document_id: UUID):
        super().__init__(
            f"Chunk with ID '{chunk_id}' and Index '{chunk_idx}' of document with ID '{document_id} 'was not found."
        )

        self.chunk_id = chunk_id
        self.chunk_idx = chunk_idx


class IngestionJobNotFoundException(NotFoundException):
    def __init__(self, job_id: UUID):
        super().__init__(f"Job with ID '{job_id}' was not found.")

        self.chunk_id = job_id


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
    """


class DatabaseInternalException(DatabaseException):
    """
    General database operation failure.
    """

class DatabaseOperationException(DatabaseException):
    """
    General database operation failure.
    """


class DatabaseConnectionException(DatabaseException):
    """
    Database unavailable or connection failed.
    """


class DatabaseTimeoutException(DatabaseException):
    """
    Database operation exceeded timeout.
    """


class EntityAlreadyExistsException(DatabaseException):
    """
    Duplicate entity creation.
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
# Event Manager Exceptions
# ============================================================
class EventHandlerException(ApplicationException):
    """
    Base exception for event handler failures.
    """


class EventHandlerProcessingException(ApplicationException):
    def __init__(
        self,
        event_type: str,
    ):
        super().__init__(
            f"Error triggered when processing MinIO 'ObjectCreated' events of type {event_type}."
        )

        self.event_type = event_type


class AIOKafkaConsumerException(EventHandlerException):
    """
    Base exception for async Kafka consumer failures.
    """


class AIOKafkaConsumerAuthException(AIOKafkaConsumerException):
    def __init__(
        self,
        topics: set[str],
    ):
        super().__init__(
            f"Access to Kafka topics '{topics}' refused due to missing permissions or bad credentials."
        )

        self.topics = topics


class AIOKafkaConsumerOffsetException(AIOKafkaConsumerException):
    def __init__(
        self, message: str = "The 'auto_offset_reset' policy has not been set"
    ):
        super().__init__(message)


class AIOKafkaConsumerRecordTooLargeException(AIOKafkaConsumerException):
    def __init__(
        self, message: str = "The message exceeds 'max_partition_fetch_bytes'."
    ):
        super().__init__(message)


class AIOKafkaConsumerInvalidMessageException(AIOKafkaConsumerException):
    def __init__(
        self,
        message: str = "The CRC check on the message failed due to connection failure or code bug.",
    ):
        super().__init__(message)

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
    """


class DocumentServiceException(ServiceException):
    """
    Document service failure.
    """


class JobServiceException(ServiceException):
    """
    Document service failure.
    """


class UserServiceException(ServiceException):
    """
    User service failure.
    """


class TenantServiceException(ServiceException):
    """
    Tenant service failure.
    """
