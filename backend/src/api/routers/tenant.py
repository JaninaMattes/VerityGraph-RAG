from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from src.core.logger import get_logger
from src.dependencies import get_tenant_service
from src.domain.tenants.dataclasses import Tenant
from src.domain.tenants.schemas import CurrentTenant, TenantResponse
from src.domain.tenants.service import TenantService

logger = get_logger("api-backend.routers.tenant")

TenantServiceDep = Annotated[TenantService, Depends(get_tenant_service)]

router = APIRouter()


@router.post("/tenants/register", status_code=status.HTTP_200_OK)
async def register(
    organisation: str,
    service: TenantServiceDep,
) -> TenantResponse:
    try:
        return await service.create(tenant=Tenant(organisation))
    except Exception as e:
        logger.exception(
            f"Creation of new tenant for organisation '{organisation}' failed!",
        )  # log internally, keep external message generic
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred while creating new tenant entry for organisation {organisation}.",
        ) from e


@router.get("/tenants/{tenant_id}", status_code=status.HTTP_200_OK)
async def read_tenant(
    tenant_id: UUID,
    service: TenantServiceDep,
) -> CurrentTenant:
    try:
        return await service.get(tenant_id=tenant_id)
    except Exception as e:
        logger.exception(
            f"Retrieval of tenant with ID {tenant_id} failed!",
        )  # log internally, keep external message generic
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred while retrieving tenant with ID {tenant_id}.",
        ) from e


@router.delete("/tenants/{tenant_id}", status_code=status.HTTP_200_OK)
async def revoke_tenant(
    tenant_id: UUID,
    service: TenantServiceDep,
) -> TenantResponse:
    try:
        return await service.delete(tenant_id=tenant_id)
    except Exception as e:
        logger.exception(
            f"Removal of tenant with ID {tenant_id} failed!",
        )  # log internally, keep external message generic
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred while removing tenant with ID {tenant_id}.",
        ) from e
