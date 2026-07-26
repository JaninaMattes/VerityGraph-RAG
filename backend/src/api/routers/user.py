from uuid import UUID

from fastapi import APIRouter, status
from src.core.logger import get_logger
from src.domain.auth.schemas import LoginResponse, RegisterResponse, UserResponse

logger = get_logger("api-backend.routers.user")

router = APIRouter()

@router.post("/users/register", status_code=status.HTTP_200_OK)
async def register() -> RegisterResponse:
    return RegisterResponse(status="SUCCESS")


@router.post("/users/login", status_code=status.HTTP_200_OK)
async def login() -> LoginResponse:
    return LoginResponse(status="SUCCESS")


@router.get("/users/{user_id}", status_code=status.HTTP_200_OK)
async def read_user(user_id: UUID) -> UserResponse:
    return UserResponse(status="SUCCESS")
