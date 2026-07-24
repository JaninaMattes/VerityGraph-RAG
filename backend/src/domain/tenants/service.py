from datetime import datetime, timezone
import uuid

from src.shared.enums import TenantStatus
from src.utils.exceptions import TenantNotFoundException
from src.application.port.tenant_repository import TenantRepository
from src.domain.tenants.schemas import CurrentTenant, Response
from src.domain.tenants.dataclasses import Tenant
from src.domain.tenants.entities import TenantEntity
from src.core.logger import get_logger

logger = get_logger("api-backend.domain.tenant.service")


class TenantService:
    """The service layer defines the business logic that ineracts with the repository."""

    def __init__(
        self,
        repository: TenantRepository,
    ) -> None:
        self.repository = repository

    async def create(self, tenant: Tenant) -> Response:
        tenant_id = uuid.uuid4()

        # Persist metadata
        now = datetime.now(timezone.utc)
        entity = TenantEntity(
            tenant_id=tenant_id,
            organisation=tenant.organisation,
            created_at=now,
            updated_at=now,
            status=TenantStatus.CREATED,
        )
        try:
            db_tenant = await self.repository.create(entity)
            return Response(tenant_id=db_tenant.tenant_id, status=db_tenant.status)
        except Exception as e:
            logger.error(
                f"Failed to create new tenant {tenant_id}. Error: {e}",
                exc_info=True,
            )
            raise

    async def get(self, tenant_id: uuid.UUID) -> CurrentTenant:
        try:
            db_tenant = await self.repository.get(tenant_id)

            if db_tenant is None:
                raise TenantNotFoundException(
                    name="Tenant Service Error",
                    message=f"Requested tenant with ID {tenant_id} not found!",
                )
            return CurrentTenant(
                tenant_id=db_tenant.tenant_id,
                organisation=db_tenant.organisation,
                status=db_tenant.status,
            )
        except Exception as e:
            logger.error(
                f"Failed to retrieve tenant {tenant_id}. Error: {e}",
                exc_info=True,
            )
            raise

    async def update(self, tenant: Tenant, tenant_id: uuid.UUID) -> Response:
        try:
            db_tenant = await self.repository.get(tenant_id)

            if db_tenant is None:
                raise TenantNotFoundException(
                    name="Tenant Service Error",
                    message=f"Requested tenant with ID {tenant_id} not found!",
                )

            # Modulate tenant details
            db_tenant.organisation = tenant.organisation
            db_tenant.mark_updated()

            # Update tenant information
            updated = await self.repository.update(db_tenant)

            return Response(tenant_id=updated.tenant_id, status=db_tenant.status)

        except Exception as e:
            logger.error(
                f"Failed to update tenant {tenant_id}. Error: {e}",
                exc_info=True,
            )
            raise

    async def delete(self, tenant_id: uuid.UUID) -> Response:
        try:
            db_tenant = await self.repository.get(tenant_id)

            if db_tenant is None:
                raise TenantNotFoundException(
                    name="Tenant Service Error",
                    message=f"Requested tenant with ID {tenant_id} not found!",
                )

            deleted_tenant = await self.repository.delete(db_tenant)
            return Response(
                tenant_id=deleted_tenant.tenant_id, status=deleted_tenant.status
            )

        except Exception as e:
            logger.error(
                f"Failed to delete tenant {tenant_id}. Error: {e}",
                exc_info=True,
            )
            raise
