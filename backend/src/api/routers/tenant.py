from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from src.dependencies import get_tenant_service
from src.domain.tenants.dataclasses import Tenant, UpdateTenant
from src.domain.tenants.service import TenantService
from src.shared.core.logger import get_logger
from src.shared.schemas.tenant import (
    CreateTenantRequest,
    TenantResponse,
    UpdateTenantRequest,
)

logger = get_logger("api.routers.tenant")

TenantServiceDep = Annotated[TenantService, Depends(get_tenant_service)]

router = APIRouter()


@router.post(
    "/tenants",
    status_code=status.HTTP_201_CREATED,
    response_model=TenantResponse,
)
async def create_tenant(
    request: CreateTenantRequest,
    service: TenantServiceDep,
) -> TenantResponse:
    return await service.create(Tenant(request.organisation))


@router.get(
    "/tenants/{tenant_id}",
    status_code=status.HTTP_200_OK,
    response_model=TenantResponse,
)
async def read_tenant(
    tenant_id: UUID,
    service: TenantServiceDep,
) -> TenantResponse:
    return await service.get(tenant_id)


@router.patch(
    "/tenants/{tenant_id}",
    status_code=status.HTTP_200_OK,
    response_model=TenantResponse,
)
async def update_tenant(
    tenant_id: UUID,
    request: UpdateTenantRequest,
    service: TenantServiceDep,
) -> TenantResponse:
    return await service.update(
        UpdateTenant(tenant_id, organisation=request.organisation)
    )


@router.delete(
    "/tenants/{tenant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_tenant(
    tenant_id: UUID,
    service: TenantServiceDep,
) -> None:
    await service.delete(tenant_id)
