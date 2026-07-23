from uuid import UUID
from pydantic import BaseModel

from src.shared.enums import TenantStatus

"""The schema module provides the building blocks for ..."""


class CreationRequest(BaseModel):
    organisation: str


class CreationResponse(BaseModel):
    status: str


class TenantResponse(BaseModel):
    status: str


class Response(BaseModel):
    tenant_id: UUID
    status: TenantStatus


class CurrentTenant(BaseModel):
    tenant_id: UUID
    organisation: str
    status: TenantStatus
