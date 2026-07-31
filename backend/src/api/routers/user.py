from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from src.core.logger import get_logger
from src.dependencies import get_user_service
from src.domain.users.dataclasses import User
from src.domain.users.schemas import (
    CurrentUser,
    RegisterRequest,
    UpdateRequest,
    UserResponse,
)
from src.domain.users.service import UserService

logger = get_logger("api.routers.user")

UserServiceDep = Annotated[UserService, Depends(get_user_service)]


router = APIRouter()


@router.post(
    "/users/register", status_code=status.HTTP_200_OK, response_model=UserResponse
)
async def register(
    tenant_id: UUID, user: RegisterRequest, service: UserServiceDep
) -> UserResponse:
    try:
        return await service.create(
            User(user.username, user.email, user.password_hash),
            tenant_id=tenant_id,
        )
    except Exception as e:
        logger.exception(
            f"Creation of new user with email {user.email!r} and name {user.username!r} failed!",
        )  # log internally, keep external message generic
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while creating new user entry.",
        ) from e


@router.get(
    "/users/{user_id}", status_code=status.HTTP_200_OK, response_model=CurrentUser
)
async def read_user(user_id: UUID, service: UserServiceDep) -> CurrentUser:
    try:
        return await service.get(user_id=user_id)
    except Exception as e:
        logger.exception(
            f"Creation of new user with ID {user_id!r} failed!",
        )  # log internally, keep external message generic
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while searching for user.",
        ) from e


@router.patch(
    "/users/{user_id}", status_code=status.HTTP_200_OK, response_model=CurrentUser
)
async def update_user(
    user_id: UUID, user: UpdateRequest, service: UserServiceDep
) -> CurrentUser:
    try:
        return await service.update(
            user_id=user_id, user=User(username=user.username, email=user.email)
        )
    except Exception as e:
        logger.exception(
            f"Creation of new user with ID {user_id!r} failed!",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while searching for user.",
        ) from e


@router.delete(
    "/users/{user_id}", status_code=status.HTTP_200_OK, response_model=UserResponse
)
async def deactivate_user(user_id: UUID, service: UserServiceDep) -> UserResponse:
    try:
        return await service.deactivate(user_id=user_id)
    except Exception as e:
        logger.exception(
            f"Deactivation of new user with ID {user_id!r} failed!",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while removing user from database.",
        ) from e
