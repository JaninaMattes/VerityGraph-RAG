from abc import abstractmethod
from typing import Protocol
from uuid import UUID

from src.domain.tenants.entities import TenantEntity


class TenantRepository(Protocol):
    """The repository layer handles all CRUD requests against a databse."""

    @abstractmethod
    async def create(
        self,
        tenant: TenantEntity,
    ) -> TenantEntity: ...

    @abstractmethod
    async def update(
        self,
        tenant: TenantEntity,
    ) -> TenantEntity: ...

    @abstractmethod
    async def get(self, tenant_id: UUID) -> TenantEntity: ...

    @abstractmethod
    async def delete(
        self,
        tenant: TenantEntity,
    ) -> TenantEntity: ...
