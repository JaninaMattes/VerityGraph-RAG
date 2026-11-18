"""HTTP endpoints for tenants. A caller can only read or change its own tenant."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.api.dependencies import get_current_tenant_id, get_tenant_service
from src.domain.tenants.dataclasses import Tenant, UpdateTenant
from src.domain.tenants.service import TenantService
from src.libs.exceptions.exceptions import TenantNotFoundException
from src.libs.schemas.tenant import (
    CreateTenantRequest,
    TenantResponse,
    UpdateTenantRequest,
)

TenantServiceDep = Annotated[TenantService, Depends(get_tenant_service)]
CurrentTenantDep = Annotated[uuid.UUID, Depends(get_current_tenant_id)]

router = APIRouter()


def ensure_own_tenant(tenant_id: uuid.UUID, current_tenant_id: uuid.UUID) -> None:
    """Raise TenantNotFoundException (404) if the path names another tenant.

    404 instead of 403 does not reveal whether the other tenant exists.
    """
    if tenant_id != current_tenant_id:
        raise TenantNotFoundException(tenant_id)


@router.post(
    "/tenants",
    status_code=status.HTTP_201_CREATED,
    response_model=TenantResponse,
)
async def create_tenant(
    request: CreateTenantRequest,
    service: TenantServiceDep,
) -> TenantResponse:
    """Create a tenant (201). A blank organisation name returns 422."""
    return TenantResponse.model_validate(
        await service.create(Tenant(request.organisation))
    )


@router.get(
    "/tenants/{tenant_id}",
    status_code=status.HTTP_200_OK,
    response_model=TenantResponse,
)
async def read_tenant(
    tenant_id: uuid.UUID,
    current_tenant_id: CurrentTenantDep,
    service: TenantServiceDep,
) -> TenantResponse:
    """Return the caller's tenant. Another or unknown tenant returns 404."""
    ensure_own_tenant(tenant_id, current_tenant_id)
    return TenantResponse.model_validate(await service.get(tenant_id))


@router.patch(
    "/tenants/{tenant_id}",
    status_code=status.HTTP_200_OK,
    response_model=TenantResponse,
)
async def update_tenant(
    tenant_id: uuid.UUID,
    request: UpdateTenantRequest,
    current_tenant_id: CurrentTenantDep,
    service: TenantServiceDep,
) -> TenantResponse:
    """Rename the caller's tenant. Another tenant returns 404; a blank name returns 422."""
    ensure_own_tenant(tenant_id, current_tenant_id)
    updated = await service.update(
        UpdateTenant(tenant_id, organisation=request.organisation)
    )
    return TenantResponse.model_validate(updated)


@router.delete(
    "/tenants/{tenant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_tenant(
    tenant_id: uuid.UUID,
    current_tenant_id: CurrentTenantDep,
    service: TenantServiceDep,
) -> None:
    """Delete the caller's tenant (204). Another or unknown tenant returns 404."""
    ensure_own_tenant(tenant_id, current_tenant_id)
    await service.delete(tenant_id)
