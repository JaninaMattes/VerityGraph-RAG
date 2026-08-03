import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from src.dependencies import (
    get_document_service,
)
from src.domain.documents.service import DocumentService
from src.shared.core.logger import get_logger
from src.shared.schemas.document import (
    CreateDocumentRequest,
    DocumentResponse,
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

    return await service.get_download_url(document_id)

@router.patch(
    "/documents/{document_id}/finalize",
    status_code=status.HTTP_200_OK,
    response_model=DocumentResponse,
)
async def finalize(
    document_id: uuid.UUID,
    service: DocServiceDep,
) -> DocumentResponse:
    """Update metdata in database, if document has been uploaded to blob storage."""
    return await service.finalize_upload(document_id)


@router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    document_id: uuid.UUID,
    service: DocServiceDep,
) -> None:
    await service.delete_document_metadata(document_id)