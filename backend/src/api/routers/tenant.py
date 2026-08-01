from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from src.core.logger import get_logger
from src.dependencies import get_tenant_service
from src.domain.tenants.dataclasses import Tenant
from src.domain.tenants.schemas import CurrentTenant, TenantResponse, UpdateRequest
from src.domain.tenants.service import TenantService
from src.utils.exceptions import (
    DatabaseException,
    NotFoundException,
    TenantServiceException,
)

logger = get_logger("api.routers.tenant")

TenantServiceDep = Annotated[TenantService, Depends(get_tenant_service)]

router = APIRouter()


@router.post(
    "/tenants/register", status_code=status.HTTP_200_OK, response_model=TenantResponse
)
async def register(
    organisation: str,
    service: TenantServiceDep,
) -> TenantResponse:
    return await service.create(tenant=Tenant(organisation))


@router.get(
    "/tenants/{tenant_id}", status_code=status.HTTP_200_OK, response_model=CurrentTenant
)
async def read_tenant(
    tenant_id: UUID,
    service: TenantServiceDep,
) -> CurrentTenant:

    return await service.get(tenant_id=tenant_id)


@router.patch(
    "/tenants/{tenant_id}", status_code=status.HTTP_200_OK, response_model=CurrentTenant
)
async def update_tenant(
    tenant_id: UUID,
    tenant: UpdateRequest,
    service: TenantServiceDep,
) -> CurrentTenant:

    return await service.update(tenant_id=tenant_id, tenant=Tenant(tenant.organisation))


@router.delete(
    "/tenants/{tenant_id}",
    status_code=status.HTTP_200_OK,
    response_model=TenantResponse,
)
async def revoke_tenant(
    tenant_id: UUID,
    service: TenantServiceDep,
) -> TenantResponse:

    return await service.delete(tenant_id=tenant_id)
