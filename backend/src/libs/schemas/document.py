"""Request and response bodies of the /documents endpoints."""

from datetime import timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.libs.enums.document import DocumentStatus
from src.libs.types import NonEmptyStr


class CreateUploadRequest(BaseModel):
    filename: NonEmptyStr
    namespace: NonEmptyStr = "files"
    mime_type: str = "application/pdf"


class DocumentStatusResponse(BaseModel):
    document_id: UUID
    status: DocumentStatus


class PresignedURLResponse(BaseModel):
    """Built from a PresignedUrl with PresignedURLResponse.model_validate(value)."""

    model_config = ConfigDict(from_attributes=True)

    document_id: UUID
    url: str
    expires_at: timedelta
    required_headers: dict[str, str]


class DeleteResponse(BaseModel):
    document_id: UUID
    status: DocumentStatus
