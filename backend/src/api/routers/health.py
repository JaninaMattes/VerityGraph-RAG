from typing import Annotated

from fastapi import APIRouter, Depends, status
from src.dependencies import get_settings
from src.shared.core.config import Settings
from src.shared.core.logger import get_logger

logger = get_logger("api.routers.health")

SettingsDep = Annotated[Settings, Depends(get_settings)]

router = APIRouter()


@router.get("/info", status_code=status.HTTP_200_OK)
async def info(settings: SettingsDep):
    return {
        "app_name": settings.app_name,
    }