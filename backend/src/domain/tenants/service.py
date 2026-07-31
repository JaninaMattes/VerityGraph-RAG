import uuid
from datetime import UTC, datetime

from src.core.logger import get_logger
from src.domain.tenants.dataclasses import Tenant
from src.domain.tenants.entities import TenantEntity
from src.domain.tenants.repository import TenantRepository
from src.domain.tenants.schemas import CurrentTenant, TenantResponse
from src.shared.enums import TenantStatus
from src.utils.exceptions import TenantNotFoundException, TenantServiceError

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
        except Exception as e:
            logger.exception(
                f"Failed to create tenant entry {tenant_id!r} in DB!",
            )
            raise TenantServiceError(
                "Tenant Service Error",
                f"Failed to create tenant entry {tenant_id!r} in DB!",
            ) from e

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
            logger.exception(
                f"Failed to retrieve tenant with ID {tenant_id!r} from database!",
            )
            raise TenantServiceError(
                "Tenant Service Error",
                f"Failed to retrieve tenant with ID {tenant_id!r} from database!",
            ) from e

    async def update(self, tenant: Tenant, tenant_id: uuid.UUID) -> CurrentTenant:
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

            return CurrentTenant(
                tenant_id=updated.tenant_id,
                organisation=updated.organisation,
                status=db_tenant.status,
            )

        except Exception as e:
            logger.exception(
                f"Failed to update tenant with ID {tenant_id!r} in database!",
            )
            raise TenantServiceError(
                "Tenant Service Error",
                f"Failed to update tenant with ID {tenant_id!r} in database!",
            ) from e

    async def deactivate(self, tenant_id: uuid.UUID) -> TenantResponse:
        try:
            db_tenant = await self.repository.get(tenant_id)

            if db_tenant is None:
                raise TenantNotFoundException(
                    name="Tenant Service Error",
                    message=f"Requested tenant with ID {tenant_id} not found!",
                )

            deleted_tenant = await self.repository.delete(db_tenant)
            return TenantResponse(
                tenant_id=deleted_tenant.tenant_id, status=deleted_tenant.status
            )

        except Exception as e:
            logger.exception(
                f"Failed to delete tenant with ID {tenant_id!r} in database!"
            )
            raise TenantServiceError(
                "Tenant Service Error",
                f"Failed to delete tenant with ID {tenant_id!r} in database!",
            ) from e