import uuid
from datetime import UTC, datetime

from src.domain.tenants.dataclasses import Tenant, UpdateTenant
from src.domain.tenants.entities import TenantEntity
from src.domain.tenants.repository import TenantRepository
from src.libs.core.logger import get_logger
from src.libs.enums.tenant import TenantStatus
from src.libs.exceptions.exceptions import (
    DatabaseException,
    NotFoundException,
    TenantNotFoundException,
    TenantServiceException,
)
from src.libs.schemas.tenant import TenantResponse

logger = get_logger("api.domain.tenant.service")


class TenantService:
    """The service layer defines the business logic that ineracts with the repository."""

    def __init__(
        self,
        repository: TenantRepository,
    ) -> None:
        self._repository = repository

    async def create(self, tenant: Tenant) -> TenantResponse:
        """Create new tenant in database."""
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
            db_tenant = await self._repository.create(entity)
            return TenantResponse(
                organisation=db_tenant.organisation,
                status=db_tenant.status,
            )
        except DatabaseException:
            raise
        except Exception as exc:
            logger.exception(
                "Unexpected error occured when creating new entry for tenant with id '%s'",
                tenant_id,
            )
            raise TenantServiceException(
                "Failed to create new tenant",
            ) from exc

    async def get(self, tenant_id: uuid.UUID) -> TenantResponse:
        """Retrieve a tenant from the database."""
        try:
            db_tenant = await self._repository.get_one(tenant_id)
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
            logger.exception(
                "Unexpected error occured when searching for tenant with id '%s'",
                tenant_id,
            )
            raise TenantServiceException(
                "Failed to find tenant information",
            ) from exc

    async def update(self, tenant: UpdateTenant) -> TenantResponse:
        """Update a tenant instance in the database."""
        try:
            db_tenant = await self._repository.get_one(tenant.tenant_id)

            # Modulate tenant details
            db_tenant.organisation = tenant.organisation
            db_tenant.mark_updated()

            # Update tenant information
            updated = await self._repository.update(db_tenant)
            return TenantResponse(
                organisation=updated.organisation,
                status=db_tenant.status,
            )
        except DatabaseException:
            raise
        except NotFoundException:
            raise
        except Exception as exc:
            logger.exception(
                "Unexpected error occured when updating tenant with id '%s",
                tenant.tenant_id,
            )
            raise TenantServiceException(
                "Failed to update tenant",
            ) from exc

    async def delete(self, tenant_id: uuid.UUID) -> None:
        """Delete a tenant instance in the database."""
        try:
            await self._repository.delete(tenant_id)
        except DatabaseException:
            raise
        except NotFoundException:
            raise
        except Exception as exc:
            logger.exception(
                "Unexpected error occured when deleting tenant with id '%s",
                tenant_id,
            )
            raise TenantServiceException(
                "Failed to delete tenant",
            ) from exc
