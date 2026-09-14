from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.api.dependencies import get_user_service
from src.domain.users.dataclasses import UpdateUser, User
from src.domain.users.service import UserService
from src.shared.core.logger import get_logger
from src.shared.schemas.user import (
    RegisterRequest,
    UpdateUserRequest,
    UserResponse,
)

logger = get_logger("api.routers.user")

UserServiceDep = Annotated[UserService, Depends(get_user_service)]


router = APIRouter()


@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def register(
    tenant_id: UUID, user: RegisterRequest, service: UserServiceDep
) -> UserResponse:
    return await service.create(
        User(user.username, user.email, user.password_hash),
        tenant_id=tenant_id,
    )

@router.get(
    "/users/{user_id}", status_code=status.HTTP_200_OK, response_model=UserResponse
)
async def read_user(user_id: UUID, service: UserServiceDep) -> UserResponse:
    return await service.get(user_id)

@router.patch(
    "/users/{user_id}", status_code=status.HTTP_200_OK, response_model=UserResponse
)
async def update_user(
    user_id: UUID, request: UpdateUserRequest, service: UserServiceDep
) -> UserResponse:
    return await service.update(
        UpdateUser(user_id, username=request.username, email=request.email)
    )

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(user_id: UUID, service: UserServiceDep) -> None:
    await service.delete(user_id=user_id)