from src.domain.tenants.entities import TenantEntity
from src.infrastructure.database.postgres.models.tenant import Tenant


class TenantMapper:
    @staticmethod
    def to_model(entity: TenantEntity) -> Tenant:
        return Tenant(
            tenant_id=entity.tenant_id,
            organisation=entity.organisation,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
            deleted_by=entity.deleted_by,
            status=entity.status,
            # DB handles created_at/updated_at on creation
        )

    @staticmethod
    def to_entity(model: Tenant) -> TenantEntity:
        return TenantEntity(
            tenant_id=model.tenant_id,
            organisation=model.organisation,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
            deleted_by=model.deleted_by,
            status=model.status,
        )
