from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.api.dependencies import get_settings
from src.shared.core.config import Settings
from src.shared.core.logger import get_logger
from src.shared.schemas.health import AppHealthResponse

logger = get_logger("api.routers.health")

SettingsDep = Annotated[Settings, Depends(get_settings)]

router = APIRouter()

@router.get("/info", status_code=status.HTTP_200_OK)
async def info(settings: SettingsDep) -> AppHealthResponse:
    """This route returns a simple message indicating the status of the application.

    Attributes
    ----------
    settings: SettingsDep
      The settings object containing configuration settings for the application.

    Returns
    -------
    dict
       A dictionary containing the name of the application.
    """
    app_name = settings.app_name
    return AppHealthResponse(app_name=app_name)
