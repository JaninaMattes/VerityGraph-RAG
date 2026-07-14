# Initialize the router instance
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import ValidationError

from src.utils.logger import get_logger


logger = get_logger("api-backend.routers.documents")

router = APIRouter()


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload(file: UploadFile = File(...)):
    if file.content_type not in {
        "video/mp4",
        "image/png",
        "image/jpeg",
        "application/pdf",
        "text/markdown",
    }:
        raise HTTPException(415, "Unsupported file type")

    try:
        data = await file.read()  # TODO: OK for small files - stream to disk directly
        return {
            "filename": file.filename,
            "type": file.content_type,
            "bytes": len(data),
        }
    except ValidationError as pydantic_err:
        # Catch strict data schema parsing errors
        logger.warning(f"Schema validation failure during ingestion: {pydantic_err}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Data integrity validation failed inside the system contract layer.",
        ) from pydantic_err

    except Exception as e:
        logger.error(
            f"Upload binary file execution failure: {e}", exc_info=True
        )  # log internally, keep external message generic
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while processing "
            "and vectorising the uploaded document.",
        ) from e


@router.post("/upload/stream", status_code=status.HTTP_201_CREATED)
async def upload_stream(file: UploadFile = File(...)):
    if file.content_type not in {
        "video/mp4",
        "image/png",
        "image/jpeg",
        "application/pdf",
        "text/markdown",
    }:
        raise HTTPException(415, "Unsupported file type")
