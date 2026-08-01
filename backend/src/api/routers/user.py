from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from src.core.logger import get_logger
from src.dependencies import get_user_service
from src.domain.users.dataclasses import UpdateUser, User
from src.domain.users.schemas import (
    CurrentUser,
    RegisterRequest,
    UpdateRequest,
    UserResponse,
)
from src.domain.users.service import UserService
from src.utils.exceptions import (
    DatabaseException,
    NotFoundException,
    UserServiceException,
)

logger = get_logger("api.routers.user")

UserServiceDep = Annotated[UserService, Depends(get_user_service)]


router = APIRouter()


@router.post(
    "/users/register", status_code=status.HTTP_200_OK, response_model=UserResponse
)
async def register(
    tenant_id: UUID, user: RegisterRequest, service: UserServiceDep
) -> UserResponse:
    return await service.create(
        User(user.username, user.email, user.password_hash),
        tenant_id=tenant_id,
    )

@router.get(
    "/users/{user_id}", status_code=status.HTTP_200_OK, response_model=CurrentUser
)
async def read_user(user_id: UUID, service: UserServiceDep) -> CurrentUser:
    return await service.get(user_id=user_id)

@router.patch(
    "/users/{user_id}", status_code=status.HTTP_200_OK, response_model=CurrentUser
)
async def update_user(
    user_id: UUID, user: UpdateRequest, service: UserServiceDep
) -> CurrentUser:
    return await service.update(
        user_id=user_id, user=UpdateUser(username=user.username, email=user.email)
    )

@router.delete(
    "/users/{user_id}", status_code=status.HTTP_200_OK, response_model=UserResponse
)
async def deactivate_user(user_id: UUID, service: UserServiceDep) -> UserResponse:
    return await service.deactivate(user_id=user_id)