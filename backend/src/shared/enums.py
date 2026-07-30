from enum import StrEnum


class StorageProvider(StrEnum):
    MINIO = "minio"
    S3 = "s3"
    AZURE = "azure"
    LOCAL = "local"


class Language(StrEnum):
    ENG = "english"


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
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PENDING = "pending"
    FAILED = "failed"
    DELETED = "deleted"
