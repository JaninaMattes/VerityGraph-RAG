from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from src.utils.exceptions import TenantNotFoundException
from src.infrastructure.database.postgres.models.tenant import Tenant
from src.infrastructure.database.postgres.mapper.tenant import TenantMapper
from src.domain.tenants.entities import TenantEntity
from src.domain.tenants.repository import TenantRepository
from src.utils.logger import get_logger

logger = get_logger("api-backend.infra.postgres.tenant")


class PostgresTenantRepository(TenantRepository):
    def __init__(
        self,
        session: AsyncSession,
    ):
        self.session = session

    async def create(
        self,
        tenant: TenantEntity,
    ) -> TenantEntity:
        db_tenant = TenantMapper.to_model(tenant)

        # Add new object to session
        try:
            self.session.add(db_tenant)
            await self.session.commit()
            await self.session.refresh(db_tenant)
        except Exception as e:
            logger.error(
                f"Failed to create new tenant with ID {tenant.tenant_id}! Error: {e}",
            )
            await self.session.rollback()
            raise

        return TenantMapper.to_entity(db_tenant)  # after rerfesh

    async def update(
        self,
        tenant: TenantEntity,
    ) -> TenantEntity:

        db_tenant = TenantMapper.to_model(tenant)

        # Merge objects
        try:
            merged_tenant = await self.session.merge(db_tenant)
            await self.session.commit()
            await self.session.refresh(merged_tenant)
        except Exception as e:
            logger.error(
                f"Failed to update tenant with ID {tenant.tenant_id}! Error: {e}",
                exc_info=True,
            )
            await self.session.rollback()
            raise

        return TenantMapper.to_entity(merged_tenant)  # after refresh

    async def get(self, tenant_id: UUID) -> TenantEntity:
        try:
            db_tenant = await self.session.get(Tenant, tenant_id)
        except Exception as e:
            logger.error(
                f"Failed to retrieve tenant with ID {tenant_id}! Error: {e}",
                exc_info=True,
            )
            await self.session.rollback()
            raise

        if db_tenant is None:
            raise TenantNotFoundException(
                name="Tenant Repository Error",
                message=f"Requested tenant with ID {tenant_id} not found!",
            )

        return TenantMapper.to_entity(db_tenant)

    async def delete(
        self,
        tenant: TenantEntity,
    ) -> TenantEntity:

        db_tenant = TenantMapper.to_model(tenant)

        try:
            merged_tenant = await self.session.merge(db_tenant)
            await self.session.delete(merged_tenant)
            await self.session.commit()
        except Exception as e:
            logger.error(
                f"Failed to delete tenant with ID {tenant.tenant_id}! Error: {e}",
                exc_info=True,
            )
            await self.session.rollback()
            raise

        return TenantMapper.to_entity(merged_tenant)
