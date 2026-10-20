from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.tenants.entities import TenantEntity
from src.domain.tenants.repository import TenantRepository
from src.infrastructure.database.postgres.mapper.tenant import TenantMapper
from src.infrastructure.database.postgres.models.tenant import Tenant
from src.libs.core.logger import get_logger
from src.libs.exceptions.exceptions import (
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
        self._session = session

    async def create(
        self,
        tenant: TenantEntity,
    ) -> TenantEntity:
        db_tenant = TenantMapper.to_model(tenant)
        try:
            # Add new object to session
            self._session.add(db_tenant)
            await self._session.flush()
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            logger.error(
                "Database error as tenant %s exists already in the database.",
                tenant.tenant_id,
            )
            raise DatabaseOperationException(
                f"Tenant '{tenant.tenant_id}' already exists in database."
            ) from exc
        except SQLAlchemyError as exc:
            await self._session.rollback()
            logger.error("Database error creating new tenant %s", tenant.tenant_id)
            raise DatabaseInternalException(
                f"Failed to create new tenant entry for '{db_tenant.tenant_id}' in the database."
            ) from exc

        # Triggers lazy load / refresh
        return TenantMapper.to_entity(db_tenant)  # after rerfesh

    async def update(
        self,
        tenant: TenantEntity,
    ) -> TenantEntity:

        db_tenant = TenantMapper.to_model(tenant)
        try:
            # Merge objects
            merged_tenant = await self._session.merge(db_tenant)
            await self._session.flush()
            await self._session.commit()
        except SQLAlchemyError as exc:
            await self._session.rollback()
            logger.error("Database error updating tenant %s", tenant.tenant_id)

            raise DatabaseInternalException(
                f"Failed to update tenant '{tenant.tenant_id}'."
            ) from exc

        # Triggers lazy load / refresh
        return TenantMapper.to_entity(merged_tenant)  # after refresh

    async def delete(self, tenant_id: UUID) -> None:

        try:
            stmt = delete(Tenant).where(Tenant.tenant_id == tenant_id)
            result = await self._session.execute(stmt)
            db_tenant = result.scalar_one_or_none()

            if db_tenant is None:
                logger.exception("A tenant with id '%s' could not be found.", tenant_id)
                raise TenantNotFoundException(tenant_id)

            await self._session.flush()

        except SQLAlchemyError as exc:
            await self._session.rollback()
            logger.error(
                "Failed to remove tenant with id '%s' in database.",
                tenant_id,
            )
            raise DatabaseInternalException(
                f"Failed to remove tenant with id '{tenant_id}' in database."
            ) from exc

    async def get_one(self, tenant_id: UUID) -> TenantEntity:
        try:
            stmt = select(Tenant).where(Tenant.tenant_id == tenant_id)
            result = await self._session.execute(stmt)
            db_tenant = result.scalar_one_or_none()

            if db_tenant is None:
                logger.exception("A tenant with id '%s' could not be found.", tenant_id)
                raise TenantNotFoundException(tenant_id)

        except SQLAlchemyError as exc:
            await self._session.rollback()
            logger.error("Database error fetching tenant %s: %s", tenant_id, exc)

            raise DatabaseInternalException(
                f"Failed to read tenant information for '{tenant_id}' in the database."
            ) from exc

        return TenantMapper.to_entity(db_tenant)
