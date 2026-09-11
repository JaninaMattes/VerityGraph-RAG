import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.api.dependencies import (
    get_document_service,
)
from src.domain.documents.service import DocumentService
from src.shared.core.logger import get_logger
from src.shared.schemas.document import (
    CreateDocumentRequest,
    PresignedURLResponse,
)

logger = get_logger("api.routers.document")

router = APIRouter()

DocServiceDep = Annotated[DocumentService, Depends(get_document_service)]


@router.post(
    "/documents",
    status_code=status.HTTP_201_CREATED,
    response_model=PresignedURLResponse,
)
async def create_upload_url(
    request: CreateDocumentRequest,
    service: DocServiceDep,
    namespace: str = "documents",
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
    return await service.create_upload_url(request, namespace=namespace)


@router.get(
    "/documents/{document_id}",
    status_code=status.HTTP_200_OK,
    response_model=PresignedURLResponse,
)
async def get_download_url(
    document_id: uuid.UUID,
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
    return await service.get_download_url(document_id)


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    document_id: uuid.UUID,
    service: DocServiceDep,
) -> None:
    """
    This route removes the metadata of a document from the database.
    When the document is set to 'DELETED' status a background cleanup service is triggered
    to also delete the file from the MinIO storage.

    Attributes
    ----------
    document_id: uuid.UUID
      The ID of the document to be deleted.
    service: DocServiceDep
     The service instance to interact with the document service

    Returns
    -------
    None
    """
    await service.remove_document(document_id)