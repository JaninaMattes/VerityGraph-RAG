# src/infrastructure/workflow_execution/temporalio/models.py

from pydantic import BaseModel, Field


class IngestionPayload(BaseModel):
    document_id: str
    bucket: str
    object_key: str
    etag: str
    size_bytes: int = Field(default=-1, description="Negative if unknown")
    mime_type: str = "application/octet-stream"
    document_type: str = "PDF"  # Inferred or passed from API
