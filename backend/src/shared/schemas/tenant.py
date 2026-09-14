
from pydantic import BaseModel

from src.shared.enums.tenant import TenantStatus

"""The schema module provides the building blocks for ..."""


class UpdateTenantRequest(BaseModel):
    organisation: str


class CreateTenantRequest(BaseModel):
    organisation: str


class TenantResponse(BaseModel):
    organisation: str
    status: TenantStatus
