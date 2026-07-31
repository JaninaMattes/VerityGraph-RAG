from fastapi import APIRouter, status
from src.core.logger import get_logger

logger = get_logger("api.routers.hello-world")


router = APIRouter()

@router.get(
    "/",
    status_code=status.HTTP_200_OK,
)
def read_root():
    return {"Hello": "World"}
