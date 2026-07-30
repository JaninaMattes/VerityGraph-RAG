from fastapi import APIRouter

from src.core.logger import get_logger

logger = get_logger("api-backend.routers.hello-world")


router = APIRouter()

@router.get("/")
def read_root():
    return {"Hello": "World"}
