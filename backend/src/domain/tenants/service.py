import uuid
from datetime import UTC, datetime

from src.domain.tenants.dataclasses import Tenant, UpdateTenant
from src.domain.tenants.entities import TenantEntity
from src.domain.tenants.repository import TenantRepository
from src.shared.core.logger import get_logger
from src.shared.enums.tenant import TenantStatus
from src.shared.exception.exceptions import (
    DatabaseException,
    NotFoundException,
    TenantNotFoundException,
    TenantServiceException,
)
from src.shared.schemas.tenant import TenantResponse

logger = get_logger("api.domain.tenant.service")


class TenantService:
    """The service layer defines the business logic that ineracts with the repository."""

    def __init__(
        self,
        repository: TenantRepository,
    ) -> None:
        self.repository = repository

    async def create(self, tenant: Tenant) -> TenantResponse:
        tenant_id = uuid.uuid4()

        # Persist metadata
        now = datetime.now(UTC)
        entity = TenantEntity(
            tenant_id=tenant_id,
            organisation=tenant.organisation,
            created_at=now,
            updated_at=now,
            status=TenantStatus.CREATED,
        )
        try:
            db_tenant = await self.repository.create(entity)
            return TenantResponse(
                organisation=db_tenant.organisation,
                status=db_tenant.status,
            )
        except DatabaseException:
            raise
        except Exception as exc:
            logger.warning(
                "Unexpected error occured when creating new entry for tenant %s: %s",
                tenant_id,
                exc,
            )
            raise TenantServiceException(
                "Failed to create new tenant.",
            ) from exc

    async def get(self, tenant_id: uuid.UUID) -> TenantResponse:
        try:
            db_tenant = await self.repository.get_one(tenant_id)
            if db_tenant is None:
                raise TenantNotFoundException(tenant_id)

            return TenantResponse(
                organisation=db_tenant.organisation,
                status=db_tenant.status,
            )
        except DatabaseException:
            raise
        except NotFoundException:
            raise
        except Exception as exc:
            logger.warning(
                "Unexpected error occured when searching for tenant %s: %s",
                tenant_id,
                exc,
            )
            raise TenantServiceException(
                "Failed to find tenant.",
            ) from exc

    async def update(self, tenant: UpdateTenant) -> TenantResponse:
        try:
            db_tenant = await self.repository.get_one(tenant.tenant_id)

            # Modulate tenant details
            db_tenant.organisation = tenant.organisation
            db_tenant.mark_updated()

            # Update tenant information
            updated = await self.repository.update(db_tenant)
            return TenantResponse(
                organisation=updated.organisation,
                status=db_tenant.status,
            )
        except DatabaseException:
            raise
        except NotFoundException:
            raise
        except Exception as exc:
            logger.warning(
                "Unexpected error occured when updating tenant %s: %s",
                tenant.tenant_id,
                exc,
            )
            raise TenantServiceException(
                "Failed to update tenant.",
            ) from exc

    async def delete(self, tenant_id: uuid.UUID) -> None:
        try:
            db_tenant = await self.repository.get_one(tenant_id)
            await self.repository.delete(db_tenant)
        except DatabaseException:
            raise
        except NotFoundException:
            raise
        except Exception as exc:
            logger.warning(
                "Unexpected error occured when deactivating tenant %s: %s",
                tenant_id,
                exc,
            )
            raise TenantServiceException(
                "Failed to remove tenant.",
            ) from exc
