"""Tenant use cases."""

import uuid
from datetime import UTC, datetime

from src.domain.tenants.dataclasses import Tenant, UpdateTenant
from src.domain.tenants.entities import TenantEntity
from src.domain.tenants.repository import TenantRepository
from src.libs.enums.tenant import TenantStatus


class TenantService:
    """Creates, reads, updates and deletes tenants.

    Repository errors (NotFoundException, DatabaseException) propagate unchanged.
    """

    def __init__(self, repository: TenantRepository) -> None:
        self._repository = repository

    async def create(self, tenant: Tenant) -> TenantEntity:
        """Store a new tenant with status CREATED and return it."""
        now = datetime.now(UTC)
        entity = TenantEntity(
            tenant_id=uuid.uuid4(),
            organisation=tenant.organisation,
            created_at=now,
            updated_at=now,
            status=TenantStatus.CREATED,
        )
        return await self._repository.create(entity)

    async def get(self, tenant_id: uuid.UUID) -> TenantEntity:
        """Return the tenant. Raise TenantNotFoundException if it does not exist."""
        return await self._repository.get_one(tenant_id)

    async def update(self, tenant: UpdateTenant) -> TenantEntity:
        """Rename the tenant and return it."""
        entity = await self._repository.get_one(tenant.tenant_id)
        entity.organisation = tenant.organisation
        entity.mark_updated()
        return await self._repository.update(entity)

    async def delete(self, tenant_id: uuid.UUID) -> None:
        """Delete the tenant. Raise TenantNotFoundException if it does not exist."""
        await self._repository.delete(tenant_id)
