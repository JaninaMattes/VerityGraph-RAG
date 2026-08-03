from enum import StrEnum


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
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"
