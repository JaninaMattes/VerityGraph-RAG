from fastapi import HTTPException, UploadFile
from src.core.logger import get_logger
from src.shared.types import SUPPORTED_DOCUMENTS

logger = get_logger("api-backend.routers.utils.validate")


def validate_file(file: UploadFile):
    # TODO extend file checks + raise custom exception
    if file.content_type not in SUPPORTED_DOCUMENTS:
        logger.exception(f"The selected MIME type {file.content_type} is not supported")
        raise HTTPException(415, "Unsupported file type")