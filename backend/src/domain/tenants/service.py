import uuid
from datetime import UTC, datetime

from src.core.logger import get_logger
from src.domain.tenants.dataclasses import Tenant
from src.domain.tenants.entities import TenantEntity
from src.domain.tenants.repository import TenantRepository
from src.domain.tenants.schemas import CurrentTenant, TenantResponse
from src.shared.enums import TenantStatus
from src.utils.exceptions import (
    DatabaseException,
    NotFoundException,
    TenantNotFoundException,
    TenantServiceException,
)

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
                tenant_id=db_tenant.tenant_id, status=db_tenant.status
            )
        except DatabaseException:
            logger.warning(
                "Raised database related error for %s. This could be due to an invalid or conflicting function argument.",
                tenant_id,
            )
            raise
        except Exception as exc:
            logger.warning(
                "Unexpected error occured when creating new entry for tenant %s.",
                tenant_id,
            )
            raise TenantServiceException(
                "Failed to create new tenant.",
            ) from exc

    async def get(self, tenant_id: uuid.UUID) -> CurrentTenant:
        try:
            db_tenant = await self.repository.get(tenant_id)
            if db_tenant is None:
                raise TenantNotFoundException(tenant_id)

            return CurrentTenant(
                tenant_id=db_tenant.tenant_id,
                organisation=db_tenant.organisation,
                status=db_tenant.status,
            )
        except DatabaseException:
            logger.warning(
                "Raised database related error for %s. This could be due to an invalid or conflicting function argument.",
                tenant_id,
            )
            raise

        except NotFoundException:
            raise

        except Exception as exc:
            logger.warning(
                "Unexpected error occured when searching for tenant %s.",
                tenant_id,
            )
            raise TenantServiceException(
                "Failed to find tenant.",
            ) from exc

    async def update(self, tenant: Tenant, tenant_id: uuid.UUID) -> CurrentTenant:
        try:
            db_tenant = await self.repository.get(tenant_id)

            # Modulate tenant details
            db_tenant.organisation = tenant.organisation
            db_tenant.mark_updated()

            # Update tenant information
            updated = await self.repository.update(db_tenant)

            return CurrentTenant(
                tenant_id=updated.tenant_id,
                organisation=updated.organisation,
                status=db_tenant.status,
            )

        except DatabaseException:
            raise

        except NotFoundException:
            raise

        except Exception as exc:
            logger.warning(
                "Unexpected error occured when updating tenant %s.",
                tenant_id,
            )
            raise TenantServiceException(
                "Failed to update tenant.",
            ) from exc

    async def delete(self, tenant_id: uuid.UUID) -> TenantResponse:
        try:
            db_tenant = await self.repository.get(tenant_id)

            deleted_tenant = await self.repository.delete(db_tenant)
            return TenantResponse(
                tenant_id=deleted_tenant.tenant_id, status=deleted_tenant.status
            )

        except DatabaseException:
            raise

        except NotFoundException:
            raise

        except Exception as exc:
            logger.warning(
                "Unexpected error occured when deactivating tenant %s.",
                tenant_id,
            )
            raise TenantServiceException(
                "Failed to remove tenant.",
            ) from exc