"""HTTP endpoints for the users of the caller's tenant."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.api.dependencies import (
    PrincipalDep,
    get_current_tenant_id,
    get_user_service,
    require_admin,
)
from src.domain.users.dataclasses import UpdateUser, User
from src.domain.users.service import UserService
from src.libs.exceptions.exceptions import PermissionDeniedException
from src.libs.schemas.user import RegisterRequest, UpdateUserRequest, UserResponse

UserServiceDep = Annotated[UserService, Depends(get_user_service)]
TenantIdDep = Annotated[uuid.UUID, Depends(get_current_tenant_id)]

router = APIRouter()


@router.post(
    "/users",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    dependencies=[Depends(require_admin)],
)
async def register(
    user: RegisterRequest, tenant_id: TenantIdDep, service: UserServiceDep
) -> UserResponse:
    """Create a user in the caller's tenant (201, admin only).

    A blank field or a password shorter than 12 characters returns 422.
    """
    created = await service.create(
        User(user.username, user.email, user.password.get_secret_value()), tenant_id
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
    principal: PrincipalDep,
    service: UserServiceDep,
) -> UserResponse:
    """Change the username and email of the caller, or of any user for an admin.

    Another user returns 403 for a non-admin; a blank field returns 422.
    """
    if not (principal.is_admin or principal.user_id == user_id):
        raise PermissionDeniedException(
            f"{principal.user_id} may not change {user_id}."
        )
    tenant_id = principal.tenant_id
    updated = await service.update(
        UpdateUser(user_id, tenant_id, request.username, request.email)
    )
    return UserResponse.model_validate(updated)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
async def deactivate_user(
    user_id: uuid.UUID, tenant_id: TenantIdDep, service: UserServiceDep
) -> None:
    """Delete a user of the caller's tenant (204, admin only). Unknown user: 404."""
    await service.delete(user_id, tenant_id)
