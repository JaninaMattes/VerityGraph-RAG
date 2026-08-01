from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.domain.tenants.entities import TenantEntity
from src.domain.tenants.repository import TenantRepository
from src.infrastructure.database.postgres.mapper.tenant import TenantMapper
from src.infrastructure.database.postgres.models.tenant import Tenant
from src.utils.exceptions import DatabaseOperationException, TenantNotFoundException

logger = get_logger("api.infra.postgres.tenant")


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
        except SQLAlchemyError as exc:
            logger.warning(
                "Raised database related error for %s. This could be due to an invalid or conflicting function argument.",
                db_tenant.tenant_id,
            )
            await self.session.rollback()

            raise DatabaseOperationException(
                f"Failed to create new tenant entry for '{db_tenant.tenant_id}' in the database."
            ) from exc

        return TenantMapper.to_entity(db_tenant)  # after rerfesh

    async def get(self, tenant_id: UUID) -> TenantEntity:
        try:
            db_tenant = await self.session.get(Tenant, tenant_id)
        except SQLAlchemyError as exc:
            logger.warning(
                "Raised database related error for %s. This could be due to an invalid or conflicting function argument.",
                tenant_id,
            )
            await self.session.rollback()

            raise DatabaseOperationException(
                f"Failed to read tenant information for '{tenant_id}' in the database."
            ) from exc

        if db_tenant is None:
            logger.warning(
                "Raised database related error for %s. The tenant could not be found.",
                tenant_id,
            )
            raise TenantNotFoundException(tenant_id)

        return TenantMapper.to_entity(db_tenant)

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
        except SQLAlchemyError as exc:
            logger.warning(
                "Raised database related error for %s. This could be due to an invalid or conflicting function argument.",
                tenant.tenant_id,
            )
            await self.session.rollback()

            raise DatabaseOperationException(
                f"Failed to update tenant information for '{tenant.tenant_id}' in the database."
            ) from exc

        return TenantMapper.to_entity(merged_tenant)  # after refresh

    async def delete(
        self,
        tenant: TenantEntity,
    ) -> TenantEntity:

        db_tenant = TenantMapper.to_model(tenant)

        try:
            merged_tenant = await self.session.merge(db_tenant)
            await self.session.delete(merged_tenant)
            await self.session.commit()
        except SQLAlchemyError as exc:
            logger.warning(
                "Raised database related error for %s. This could be due to an invalid or conflicting function argument.",
                tenant.tenant_id,
            )
            await self.session.rollback()

            raise DatabaseOperationException(
                f"Failed to remove tenant information for '{tenant.tenant_id}' in the database."
            ) from exc

        return TenantMapper.to_entity(merged_tenant)
