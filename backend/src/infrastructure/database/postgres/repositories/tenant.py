from uuid import UUID

from sqlalchemy import delete, select

from src.domain.tenants.entities import TenantEntity
from src.domain.tenants.repository import TenantRepository
from src.infrastructure.database.postgres.mapper.tenant import TenantMapper
from src.infrastructure.database.postgres.models.tenant import Tenant
from src.infrastructure.database.postgres.repositories.base import (
    PostgresRepository,
    translate_db_errors,
)
from src.libs.exceptions.exceptions import TenantNotFoundException


class PostgresTenantRepository(PostgresRepository, TenantRepository):
    """Tenants in PostgreSQL."""

    async def create(self, tenant: TenantEntity) -> TenantEntity:
        """Insert the tenant. A duplicate raises DatabaseOperationException."""
        return TenantMapper.to_entity(await self._add(TenantMapper.to_model(tenant)))

    async def update(self, tenant: TenantEntity) -> TenantEntity:
        return TenantMapper.to_entity(await self._merge(TenantMapper.to_model(tenant)))

    async def delete(self, tenant_id: UUID) -> None:
        await self._delete_one(
            delete(Tenant).where(Tenant.tenant_id == tenant_id),
            TenantNotFoundException(tenant_id),
        )

    async def get_one(self, tenant_id: UUID) -> TenantEntity:
        row = await self._scalar_one(
            select(Tenant).where(Tenant.tenant_id == tenant_id),
            TenantNotFoundException(tenant_id),
        )
        return TenantMapper.to_entity(row)

    async def find_by_organisation(self, organisation: str) -> TenantEntity | None:
        """Return a tenant with this exact organisation name, or None."""
        statement = select(Tenant).where(Tenant.organisation == organisation).limit(1)
        with translate_db_errors("find a tenant by organisation"):
            row = (await self._session.execute(statement)).scalar_one_or_none()
        return TenantMapper.to_entity(row) if row else None
