# Initialize the router instance
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import ValidationError

from src.domain.documents.schemas import Response, URLResponse
from src.domain.documents.dataclasses import DocumentStream
from src.domain.documents.service import DocumentService
from src.api.utils.validate import validate_file
from src.utils.logger import get_logger


logger = get_logger("api-backend.routers.documents")

router = APIRouter()

@router.post("/upload", response_model=URLResponse, status_code=status.HTTP_200_OK)
async def create_upload_url(
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(DocumentService),
):
    tenant_id = current_user.tenant_id
    try:
        return await service.create_upload_url(tenant_id)
    except Exception as e:
        logger.error(
            f"Generation of presigned URL failure! Error: {e}", exc_info=True
        )  # log internally, keep external message generic
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while generating the presigned upload URL.",
        ) from e


@router.get(
    "/{document_id}/download",
    response_model=URLResponse,
    status_code=status.HTTP_200_OK,
)
async def create_download_url(
    document_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(DocumentService),
):
    tenant_id = current_user.tenant_id
    try:
        return await service.create_download_url(document_id, tenant_id)
    except Exception as e:
        logger.error(
            f"Upload binary file execution failure: {e}", exc_info=True
        )  # log internally, keep external message generic
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while generating the presigned download URL.",
        ) from e


@router.post(
    "/upload/stream", response_model=Response, status_code=status.HTTP_201_CREATED
)
async def upload_documents(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(DocumentService),
):
    validate_file(file)
    tenant_id = current_user.tenant_id

    try:
        document = DocumentStream(
            stream=file.file,
            filename=file.filename if file.filename else "",
            content_type=file.content_type,
            size_bytes=file.size,
        )
        return await service.create(document, tenant_id=tenant_id)

    except Exception as e:
        logger.error(
            f"Upload binary file execution failure: {e}", exc_info=True
        )  # log internally, keep external message generic
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while processing "
            "and vectorising the uploaded document.",
        ) from e

@router.delete(
    "/{document_id}/delete", response_model=Response, status_code=status.HTTP_200_OK
)
async def delete_documents(
    document_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(DocumentService),
):
    tenant_id = current_user.tenant_id

    try:
        return await service.delete(document_id, tenant_id)

    except Exception as e:
        logger.error(
            f"Delete binary file execution failure: {e}", exc_info=True
        )  # log internally, keep external message generic
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while processing "
            "and removing the document from storage.",
        ) from e
