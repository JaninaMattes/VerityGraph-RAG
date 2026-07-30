import uuid
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from src.core.logger import get_logger
from fastapi import APIRouter, Depends, HTTPException, status
from src.core.logger import get_logger
from src.dependencies import (
    get_current_user,
    get_document_service,
)
from src.domain.auth.dataclasses import Principal
from src.domain.documents.schemas import CreateResponse, DeleteResponse, URLResponse
from src.domain.documents.schemas import CreateResponse, DeleteResponse, URLResponse
from src.domain.documents.service import DocumentService

logger = get_logger("api-backend.routers.document")

router = APIRouter()

DocServiceDep = Annotated[DocumentService, Depends(get_document_service)]
CurrentUserDep = Annotated[Principal, Depends(get_current_user)]


@router.post("/documents/upload", status_code=status.HTTP_200_OK)
async def create_upload_url(
    service: DocServiceDep,
    current_user: CurrentUserDep,
) -> URLResponse:
    tenant_id = current_user.tenant_id
    try:
        return await service.create_upload_url(tenant_id)
    except Exception as e:
        logger.exception(
            f"Creation of presigned upload URL for user with ID '{current_user.user_id}' failed!",
        )  # log internally, keep external message generic
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while generating the presigned upload URL.",
        ) from e


@router.post("/documents/{document_id}/complete", status_code=status.HTTP_200_OK)
async def create_metadata(
    document_id: uuid.UUID,
    service: DocServiceDep,
    current_user: CurrentUserDep,
) -> CreateResponse: ...


@router.post("/documents/{document_id}/complete", status_code=status.HTTP_200_OK)
async def create_metadata(
    document_id: uuid.UUID,
    service: DocServiceDep,
    current_user: CurrentUserDep,
) -> CreateResponse: ...


@router.get(
    "/documents/{document_id}/download",
    status_code=status.HTTP_200_OK,
)
async def create_download_url(
    document_id: uuid.UUID,
    service: DocServiceDep,
    current_user: CurrentUserDep,
) -> URLResponse:
    tenant_id = current_user.tenant_id
    try:
        return await service.create_download_url(document_id, tenant_id)
    except Exception as e:
        logger.exception(
            f"Creation of presigned download URL for document with ID '{document_id}' failed!",
        )  # log internally, keep external message generic
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while generating the presigned download URL.",
        ) from e


@router.delete(
    "/documents/{document_id}/delete",
    status_code=status.HTTP_200_OK,
)
async def delete_documents(
    document_id: uuid.UUID,
    service: DocServiceDep,
    current_user: CurrentUserDep,
) -> DeleteResponse:
    tenant_id = current_user.tenant_id

    try:
        return await service.delete(document_id, tenant_id)

    except Exception as e:
        logger.exception(
            f"Deletion of document with ID '{document_id}' failed!",
        )  # log internally, keep external message generic
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while processing "
            "and removing the document from storage.",
        ) from e
