"""Request and response bodies of the /documents endpoints."""

from datetime import timedelta
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.libs.enums.document import DocumentStatus
from src.libs.schemas.base import RequestModel
from src.libs.types import NonEmptyStr


class CreateUploadRequest(RequestModel):
    filename: NonEmptyStr
    namespace: NonEmptyStr = "files"


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


class BoundingBoxResponse(BaseModel):
    """A rectangle on a page in PDF points; with origin BOTTOMLEFT, top > bottom."""

    model_config = ConfigDict(from_attributes=True)

    left: float
    top: float
    right: float
    bottom: float
    origin: str


class ChunkSpanResponse(BaseModel):
    """Where one part of the chunk comes from; the client highlights `bbox`."""

    model_config = ConfigDict(from_attributes=True)

    source_ref: str
    label: str
    page_no: int | None
    bbox: BoundingBoxResponse | None
    char_start: int | None
    char_end: int | None


class ChunkResponse(BaseModel):
    """Built from a domain Chunk with ChunkResponse.model_validate(chunk)."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    token_count: int
    headings: list[str]
    page_start: int | None
    page_end: int | None
    spans: list[ChunkSpanResponse]
