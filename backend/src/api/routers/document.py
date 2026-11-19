"""HTTP endpoints for presigned document upload and download URLs."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.api.dependencies import (
    get_chunk_service,
    get_current_tenant_id,
    get_document_service,
)
from src.domain.chunks.service import ChunkService
from src.domain.documents.service import DocumentService
from src.libs.schemas.document import (
    ChunkResponse,
    CreateUploadRequest,
    PresignedURLResponse,
)

router = APIRouter()

DocServiceDep = Annotated[DocumentService, Depends(get_document_service)]
ChunkServiceDep = Annotated[ChunkService, Depends(get_chunk_service)]
TenantIdDep = Annotated[uuid.UUID, Depends(get_current_tenant_id)]


@router.post(
    "/documents",
    status_code=status.HTTP_201_CREATED,
    response_model=PresignedURLResponse,
)
async def create_upload_url(
    request: CreateUploadRequest,
    tenant_id: TenantIdDep,
    service: DocServiceDep,
) -> PresignedURLResponse:
    """Return a presigned URL to upload one document directly to storage (201).

    The client must send `required_headers` with the PUT request. A blank filename
    or namespace returns 422.
    """
    presigned = await service.create_upload_url(
        tenant_id=tenant_id,
        filename=request.filename,
        namespace=request.namespace,
    )
    return PresignedURLResponse.model_validate(presigned)


@router.get(
    "/documents/{document_id}",
    status_code=status.HTTP_200_OK,
    response_model=PresignedURLResponse,
)
async def get_download_url(
    document_id: uuid.UUID,
    tenant_id: TenantIdDep,
    service: DocServiceDep,
) -> PresignedURLResponse:
    """Return a presigned URL to download a document of the caller's tenant.

    An unknown document returns 404.
    """
    presigned = await service.get_download_url(document_id, tenant_id)
    return PresignedURLResponse.model_validate(presigned)


@router.get(
    "/documents/{document_id}/chunks",
    status_code=status.HTTP_200_OK,
    response_model=list[ChunkResponse],
)
async def list_chunks(
    document_id: uuid.UUID,
    tenant_id: TenantIdDep,
    service: ChunkServiceDep,
) -> list[ChunkResponse]:
    """Return the chunks of a document in order, with page and box per span.

    The list is empty until the ingestion has processed the document. An unknown
    document returns 404.
    """
    chunks = await service.list_for_document(document_id, tenant_id)
    return [ChunkResponse.model_validate(chunk) for chunk in chunks]
