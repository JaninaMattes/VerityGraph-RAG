# src/infrastructure/workflow_execution/temporalio/models.py


from pydantic import BaseModel, Field

"""Temporal only operate with primitives."""

class IngestionPayload(BaseModel):
    document_id: str
    tenant_id: str
    filename: str
    bucket_name: str
    object_key: str
    etag: str
    size_bytes: int = Field(default=-1, description="Negative if unknown")
    mime_type: str = "application/octet-stream"
    document_type: str = "PDF"  # Inferred or passed from API


class CreateDocumentPayload(BaseModel):
    document_id: str
    tenant_id: str
    filename: str
    bucket_name: str
    storage_key: str
    mime_type: str = "application/octet-stream"
    document_type: str = "PDF"
    status: str = "UPLOAD_PENDING"
    storage_type: str = "LOCAL"


class UpdateDocumentPayload(BaseModel):
    document_id: str
    tenant_id: str
    size_bytes: int
    bucket_name: str
    status: str = "UPLOAD_PENDING"


class ProcessDocumentPayload(BaseModel):
    document_id: str
    filename: str
    bucket: str
    object_key: str
    etag: str
    size_bytes: int
    mime_type: str = "application/octet-stream"


class ProcessDocumentResult(BaseModel):
    document_id: str
    chunks_processed: int
    status: str = "UPLOAD_PENDING"


class CreateIngestionJobPayload(BaseModel):
    job_id: str
    document_id: str
    workflow_id: str
    workflow_run_id: str
    current_stage: str = "INITIALISING"
    status: str = "PENDING"


class UpdateIngestionJobPayload(BaseModel):
    job_id: str
    document_id: str
    status: str = "PENDING"
    current_stage: str | None = None
    error_message: str | None = None