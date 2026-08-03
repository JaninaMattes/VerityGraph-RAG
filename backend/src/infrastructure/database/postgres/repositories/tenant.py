from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.shared.core.logger import get_logger
from src.domain.tenants.entities import TenantEntity
from src.domain.tenants.repository import TenantRepository
from src.infrastructure.database.postgres.mapper.tenant import TenantMapper
from src.infrastructure.database.postgres.models.tenant import Tenant
from src.shared.exception.exceptions import (
    DatabaseInternalException,
    DatabaseOperationException,
    TenantNotFoundException,
)

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
        try:
            # Add new object to session
            self.session.add(db_tenant)
            await self.session.commit()
            await self.session.refresh(db_tenant)
        except IntegrityError as exc:
            logger.warning(
                "Database error as new tenant %s exists already: %s",
                tenant.tenant_id,
                exc,
            )
            raise DatabaseOperationException(
                f"Tenant '{tenant.tenant_id}' already exists in database."
            ) from exc
        except SQLAlchemyError as exc:
            logger.warning(
                "Database error creating new tenant %s: %s", db_tenant.tenant_id, exc
            )
            await self.session.rollback()
            raise DatabaseInternalException(
                f"Failed to create new tenant entry for '{db_tenant.tenant_id}' in the database."
            ) from exc
        return TenantMapper.to_entity(db_tenant)  # after rerfesh

    async def get_one(self, tenant_id: UUID) -> TenantEntity:
        try:
            stmt = select(Tenant).where(Tenant.tenant_id == tenant_id)
            result = await self.session.execute(stmt)
            db_tenant: Tenant | None = result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            logger.warning("Database error fetching tenant %s: %s", tenant_id, exc)
            await self.session.rollback()
            raise DatabaseInternalException(
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
        try:
            # Merge objects
            merged_tenant = await self.session.merge(db_tenant)
            await self.session.commit()
            await self.session.refresh(merged_tenant)
        except SQLAlchemyError as exc:
            logger.warning(
                "Database error updating tenant %s: %s", db_tenant.tenant_id, exc
            )
            await self.session.rollback()
            raise DatabaseInternalException(
                f"Failed to update tenant information for '{tenant.tenant_id}' in the database."
            ) from exc

        return TenantMapper.to_entity(merged_tenant)  # after refresh

    async def delete(
        self,
        tenant: TenantEntity,
    ) -> None:

        db_tenant = TenantMapper.to_model(tenant)

        try:
            merged_tenant = await self.session.merge(db_tenant)
            await self.session.delete(merged_tenant)
            await self.session.commit()
        except SQLAlchemyError as exc:
            logger.warning(
                "Database error removing tenant %s: %s", db_tenant.tenant_id, exc
            )
            await self.session.rollback()
            raise DatabaseInternalException(
                f"Failed to remove tenant information for '{tenant.tenant_id}' in the database."
            ) from exc
