import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from src.core.logger import get_logger
from src.dependencies import (
    get_current_user,
    get_document_service,
)
from src.domain.auth.dataclasses import Principal
from src.domain.documents.schemas import (
    DeleteResponse,
    MetadataRequest,
    MetadataResponse,
    URLResponse,
)
from src.domain.documents.service import DocumentService

logger = get_logger("api.routers.document")

router = APIRouter()

DocServiceDep = Annotated[DocumentService, Depends(get_document_service)]
CurrentUserDep = Annotated[Principal, Depends(get_current_user)]


@router.post(
    "/documents/upload", status_code=status.HTTP_200_OK, response_model=URLResponse
)
async def create_upload_url(
    file: MetadataRequest,
    service: DocServiceDep,
    current_user: CurrentUserDep,
    namespace: str = "documents",
) -> URLResponse:

    return await service.create_upload_url(file=file, namespace=namespace)


@router.get(
    "/documents/{document_id}/download",
    status_code=status.HTTP_200_OK,
    response_model=URLResponse,
)
async def create_download_url(
    document_id: uuid.UUID,
    service: DocServiceDep,
    current_user: CurrentUserDep,
) -> URLResponse:

    return await service.create_download_url(document_id)

@router.patch(
    "/documents/{document_id}/complete",
    status_code=status.HTTP_200_OK,
    response_model=MetadataResponse,
)
async def complete(
    document_id: uuid.UUID,
    service: DocServiceDep,
    current_user: CurrentUserDep,
) -> MetadataResponse:

    return await service.update_metadata(document_id)


@router.delete(
    "/documents/{document_id}/delete",
    status_code=status.HTTP_200_OK,
    response_model=DeleteResponse,
)
async def remove_document(
    document_id: uuid.UUID,
    service: DocServiceDep,
    current_user: CurrentUserDep,
) -> DeleteResponse:

    # TODO: Retrieve current user
    user_id = current_user.user_id
    return await service.delete(document_id, user_id)