from datetime import timedelta
from uuid import UUID

from pydantic import BaseModel

from src.libs.enums.document import DocumentStatus

"""The schema module provides the building blocks for the application."""


class CreateUploadRequest(BaseModel):
    filename: str
    namespace: str = "files"
    mime_type: str = "application/pdf"


class DocumentStatusResponse(BaseModel):
    document_id: UUID
    status: DocumentStatus


class PresignedURLResponse(BaseModel):
    document_id: UUID
    url: str
    expires_at: timedelta
    required_headers: dict[str, str]


class DeleteResponse(BaseModel):
    document_id: UUID
    status: DocumentStatus
