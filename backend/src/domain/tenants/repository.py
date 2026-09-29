from typing import Protocol
from uuid import UUID

from src.domain.tenants.entities import TenantEntity


class TenantRepository(Protocol):
    """The repository layer handles all CRUD requests against a databse."""

    async def create(
        self,
        tenant: TenantEntity,
    ) -> TenantEntity:
        raise NotImplementedError("Subclasses must implement create method")

    async def get_one(self, tenant_id: UUID) -> TenantEntity:
        raise NotImplementedError("Subclasses must implement get_one method")

    async def update(
        self,
        tenant: TenantEntity,
    ) -> TenantEntity:
        raise NotImplementedError("Subclasses must implement update method")

    async def delete(
        self,
        tenant: TenantEntity,
    ) -> None:
        raise NotImplementedError("Subclasses must implement delete method")
