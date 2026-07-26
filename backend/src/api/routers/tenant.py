from uuid import UUID

from fastapi import APIRouter, status
from src.core.logger import get_logger
from src.domain.tenants.schemas import CreationResponse, TenantResponse

logger = get_logger("api-backend.routers.tenant")


router = APIRouter()


@router.post("/tenants/register", status_code=status.HTTP_200_OK)
async def register() -> CreationResponse:
    return CreationResponse(status="SUCCESS")


@router.get("/tenants/{tenant_id}", status_code=status.HTTP_200_OK)
async def read_tenant(tenant_id: UUID) -> TenantResponse:
    return TenantResponse(status="SUCCESS")
