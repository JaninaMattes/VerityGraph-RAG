import uuid
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import get_current_tenant_id, get_user_service
from src.domain.users.dataclasses import UpdateUser, User
from src.domain.users.service import UserService
from src.libs.core.logger import get_logger
from src.libs.schemas.user import (
    RegisterRequest,
    UpdateUserRequest,
    UserResponse,
)

logger = get_logger("api.routers.user")

UserServiceDep = Annotated[UserService, Depends(get_user_service)]
TenantIdDep = Annotated[uuid.UUID, Depends(get_current_tenant_id)]

router = APIRouter()


@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def register(
    user: RegisterRequest, tenant_id: TenantIdDep, service: UserServiceDep
) -> UserResponse:
    username = user.username
    email = user.email
    if not username or not username.strip():
        raise HTTPException(
            status_code=400,
            detail="Missing required parameter 'username'",
        )
    if not email or not email.strip():
        raise HTTPException(
            status_code=400,
            detail="Missing required parameter 'email'",
        )
    return await service.create(
        User(username, user.email, user.password_hash), tenant_id
    )


@router.get(
    "/users/{user_id}", status_code=status.HTTP_200_OK, response_model=UserResponse
)
async def read_user(
    user_id: UUID, tenant_id: TenantIdDep, service: UserServiceDep
) -> UserResponse:
    return await service.get(user_id, tenant_id)


@router.patch(
    "/users/{user_id}", status_code=status.HTTP_200_OK, response_model=UserResponse
)
async def update_user(
    user_id: UUID,
    request: UpdateUserRequest,
    tenant_id: TenantIdDep,
    service: UserServiceDep,
) -> UserResponse:
    username = request.username
    email = request.email
    if not username or not username.strip():
        raise HTTPException(
            status_code=400,
            detail="Missing required parameter 'username'",
        )
    if not email or not email.strip():
        raise HTTPException(
            status_code=400,
            detail="Missing required parameter 'email'",
        )
    return await service.update(UpdateUser(user_id, tenant_id, username, email))


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: UUID, tenant_id: TenantIdDep, service: UserServiceDep
) -> None:
    await service.delete(user_id, tenant_id)
