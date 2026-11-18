"""HTTP endpoints for presigned document upload and download URLs."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.api.dependencies import get_current_tenant_id, get_document_service
from src.domain.documents.service import DocumentService
from src.libs.schemas.document import CreateUploadRequest, PresignedURLResponse

router = APIRouter()

DocServiceDep = Annotated[DocumentService, Depends(get_document_service)]
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
