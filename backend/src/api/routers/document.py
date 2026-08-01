import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
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
from src.utils.exceptions import (
    DatabaseException,
    DocumentServiceException,
    NotFoundException,
    StorageException,
)

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
    try:
        return await service.create_upload_url(file=file, namespace=namespace)
    except DatabaseException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc

    except StorageException as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=exc.message
        ) from exc

    except DocumentServiceException as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


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
    try:
        return await service.create_download_url(document_id)
    except DatabaseException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc

    except StorageException as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=exc.message
        ) from exc

    except DocumentServiceException as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc

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
    try:
        return await service.update_metadata(document_id)
    except DatabaseException as exc:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=exc.message,
        ) from exc

    except NotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.message
        ) from exc

    except DocumentServiceException as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc


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

    # Retrieve current user
    user_id = current_user.user_id

    try:
        return await service.delete(document_id, user_id)

    except DatabaseException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message
        ) from exc

    except NotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.message
        ) from exc

    except DocumentServiceException as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=exc.message
        ) from exc