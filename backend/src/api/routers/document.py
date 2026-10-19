import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import get_current_tenant_id, get_document_service
from src.domain.documents.service import DocumentService
from src.libs.core.logger import get_logger
from src.libs.schemas.document import (
    CreateUploadRequest,
    PresignedURLResponse,
)

logger = get_logger("api.routers.document")

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
    """This route generates a presigned MinIO URL for the upload of a document.

    Attributes
    ----------
    requests: CreateDocumentRequest
       The request body containing the filename and tenant_id.
    service: DocumentService
       The service instance to interact with the document service

    Returns
    -------
    PresignedURLResponse
       The response containing the presigned URL and expiration time.
    """
    filename = request.filename
    namespace = request.namespace
    if not filename or not filename.strip():
        raise HTTPException(
            status_code=400,
            detail="Missing required parameter 'filename' or parameter only contains whitespace.",
        )
    if not namespace or not namespace.strip():
        raise HTTPException(
            status_code=400,
            detail="Missing required parameter 'namespace' or parameter only contains whitespace.",
        )
    return await service.create_upload_url(
        tenant_id=tenant_id,
        filename=filename,
        namespace=namespace,
    )


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
    """
    This route generates a presigned MinIO URL for the download of a document.

    Attributes
    ----------
    document_id: uuid.UUID
       The ID of the document to be downloaded.
    service: DocServiceDep
      The service instance to interact with the document service

    Returns
    -------
    PresignedURL
      The response containing the presigned URL and expiration
    """
    """
    This route generates a presigned MinIO URL for the download of a document.

    Attributes
    ----------
    document_id: uuid.UUID
       The ID of the document to be downloaded.
    service: DocServiceDep
      The service instance to interact with the document service

    Returns
    -------
    PresignedURL
      The response containing the presigned URL and expiration
    """
    return await service.get_download_url(document_id, tenant_id)