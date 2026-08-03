from datetime import timedelta
from uuid import UUID

from pydantic import BaseModel

from src.shared.enums.document import DocumentStatus

"""The schema module provides the building blocks for ..."""


class CreateDocumentRequest(BaseModel):
    filename: str
    tenant_id: UUID


class DocumentResponse(BaseModel):
    document_id: UUID
    status: DocumentStatus


class PresignedURLResponse(BaseModel):
    document_id: UUID
    url: str
    expires_at: timedelta


class DeleteResponse(BaseModel):
    document_id: UUID
    status: DocumentStatus
