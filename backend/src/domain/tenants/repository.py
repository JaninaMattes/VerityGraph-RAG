from typing import Protocol
from uuid import UUID

from src.domain.tenants.entities import TenantEntity


class TenantRepository(Protocol):
    """The repository layer handles all CRUD requests against a databse."""

    async def create(
        self,
        tenant: TenantEntity,
    ) -> TenantEntity: ...

    async def update(
        self,
        tenant: TenantEntity,
    ) -> TenantEntity: ...

    async def get_one(self, tenant_id: UUID) -> TenantEntity: ...

    async def delete(
        self,
        tenant: TenantEntity,
    ) -> None: ...
