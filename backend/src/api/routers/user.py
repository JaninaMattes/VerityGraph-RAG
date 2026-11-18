"""HTTP endpoints for the users of the caller's tenant."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.api.dependencies import get_current_tenant_id, get_user_service
from src.domain.users.dataclasses import UpdateUser, User
from src.domain.users.service import UserService
from src.libs.schemas.user import RegisterRequest, UpdateUserRequest, UserResponse

UserServiceDep = Annotated[UserService, Depends(get_user_service)]
TenantIdDep = Annotated[uuid.UUID, Depends(get_current_tenant_id)]

router = APIRouter()


@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def register(
    user: RegisterRequest, tenant_id: TenantIdDep, service: UserServiceDep
) -> UserResponse:
    """Create a user in the caller's tenant (201). A blank field returns 422."""
    created = await service.create(
        User(user.username, user.email, user.password_hash), tenant_id
    )
    return UserResponse.model_validate(created)


@router.get(
    "/users/{user_id}", status_code=status.HTTP_200_OK, response_model=UserResponse
)
async def read_user(
    user_id: uuid.UUID, tenant_id: TenantIdDep, service: UserServiceDep
) -> UserResponse:
    """Return a user of the caller's tenant. An unknown user returns 404."""
    return UserResponse.model_validate(await service.get(user_id, tenant_id))


@router.patch(
    "/users/{user_id}", status_code=status.HTTP_200_OK, response_model=UserResponse
)
async def update_user(
    user_id: uuid.UUID,
    request: UpdateUserRequest,
    tenant_id: TenantIdDep,
    service: UserServiceDep,
) -> UserResponse:
    """Change the username and email. A blank field returns 422."""
    updated = await service.update(
        UpdateUser(user_id, tenant_id, request.username, request.email)
    )
    return UserResponse.model_validate(updated)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: uuid.UUID, tenant_id: TenantIdDep, service: UserServiceDep
) -> None:
    """Delete a user of the caller's tenant (204). An unknown user returns 404."""
    await service.delete(user_id, tenant_id)
