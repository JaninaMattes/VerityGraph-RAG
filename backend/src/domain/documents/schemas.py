from datetime import timedelta
from uuid import UUID
from pydantic import BaseModel

from src.shared.enums import DocumentStatus

"""The schema module provides the building blocks for ..."""

class CreateResponse(BaseModel):
    document_id: UUID
    status: DocumentStatus

class DeleteResponse(BaseModel):
    document_id: UUID
    status: DocumentStatus


class URLResponse(BaseModel):
    url: str
    storage_key: str
    expires_at: timedelta
