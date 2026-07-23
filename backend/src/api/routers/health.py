from typing import Annotated

from fastapi import Depends

from src.api.router import router
from src.core.config import Settings
from src.dependencies import get_settings
from src.utils.logger import get_logger

logger = get_logger("api-backend.routers.health")


@router.get("/info")
async def info(settings: Annotated[Settings, Depends(get_settings)]):
    return {
        "app_name": settings.app_name,
    }
