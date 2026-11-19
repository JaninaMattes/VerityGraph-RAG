"""Request and response bodies of the /tenants endpoints."""

from pydantic import BaseModel, ConfigDict

from src.libs.enums.tenant import TenantStatus
from src.libs.schemas.base import RequestModel
from src.libs.types import NonEmptyStr


class UpdateTenantRequest(RequestModel):
    organisation: NonEmptyStr


class CreateTenantRequest(RequestModel):
    organisation: NonEmptyStr


class TenantResponse(BaseModel):
    """Built from a TenantEntity with TenantResponse.model_validate(entity)."""

    model_config = ConfigDict(from_attributes=True)

    organisation: str
    status: TenantStatus
