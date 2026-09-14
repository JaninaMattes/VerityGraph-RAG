from datetime import timedelta
from uuid import UUID

from pydantic import BaseModel

from src.shared.enums.document import DocumentStatus

"""The schema module provides the building blocks for the application."""

class CreateUploadRequest(BaseModel):
    filename: str
    content_type: str
    namespace: str = "documents"

class DocumentStatusResponse(BaseModel):
    document_id: UUID
    status: DocumentStatus


class PresignedURLResponse(BaseModel):
    document_id: UUID
    url: str
    expires_at: timedelta


class DeleteResponse(BaseModel):
    document_id: UUID
    status: DocumentStatus
