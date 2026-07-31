from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from src.core.logger import get_logger
from src.dependencies import get_tenant_service
from src.domain.tenants.dataclasses import Tenant
from src.domain.tenants.schemas import CurrentTenant, TenantResponse, UpdateRequest
from src.domain.tenants.service import TenantService

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
    try:
        return await service.create(tenant=Tenant(organisation))
    except Exception as e:
        logger.exception(
            f"Creation of new tenant for organisation {organisation!r} failed!",
        )  # log internally, keep external message generic
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while creating new tenant entry in the database.",
        ) from e

@router.get(
    "/tenants/{tenant_id}", status_code=status.HTTP_200_OK, response_model=CurrentTenant
)
async def read_tenant(
    tenant_id: UUID,
    service: TenantServiceDep,
) -> CurrentTenant:
    try:
        return await service.get(tenant_id=tenant_id)
    except Exception as e:
        logger.exception(
            f"Retrieval of tenant with ID {tenant_id!r} failed!",
        )  # log internally, keep external message generic
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while searching for tenant.",
        ) from e


@router.patch(
    "/tenants/{tenant_id}", status_code=status.HTTP_200_OK, response_model=CurrentTenant
)
async def update_tenant(
    tenant_id: UUID,
    tenant: UpdateRequest,
    service: TenantServiceDep,
) -> CurrentTenant:
    try:
        return await service.update(
            tenant_id=tenant_id, tenant=Tenant(tenant.organisation)
        )
    except Exception as e:
        logger.exception(
            f"Retrieval of tenant with ID {tenant_id!r} failed!",
        )  # log internally, keep external message generic
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while searching for tenant.",
        ) from e


@router.delete(
    "/tenants/{tenant_id}",
    status_code=status.HTTP_200_OK,
    response_model=TenantResponse,
)
async def revoke_tenant(
    tenant_id: UUID,
    service: TenantServiceDep,
) -> TenantResponse:
    try:
        return await service.deactivate(tenant_id=tenant_id)
    except Exception as e:
        logger.exception(
            f"Deactivation of tenant with ID {tenant_id!r} failed!",
        )  # log internally, keep external message generic
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while removing a tenant from database.",
        ) from e
