from enum import StrEnum


class StorageProvider(StrEnum):
    MINIO = "minio"
    S3 = "s3"
    AZURE = "azure"
    LOCAL = "local"

class TenantStatus(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class UserStatus(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    DISABLED = "disabled"


class UserRole(StrEnum):
    ADMIN = "admin"
    USER = "user"


class CredentialStatus(StrEnum):
    CREATED = "created"
    VALID = "valid"
    REVOKED = "revoked"


class LanguageType(StrEnum):
    ENGLISH = "english"


class DocumentType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    MARKDOWN = "markdown"
    CSV = "csv"
    HTML = "html"
    IMAGE = "image"
    PPTX = "pptx"


class DocumentStatus(StrEnum):
    UPLOAD_PENDING = "pending"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class IngestionStage(StrEnum):
    DOWNLOAD = "download"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    GRAPH_BUILDING = "graph_building"
    EVALUATION = "evaluation"


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"