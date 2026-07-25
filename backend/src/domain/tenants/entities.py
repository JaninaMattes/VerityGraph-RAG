from datetime import UTC, datetime
from uuid import UUID

from src.shared.enums import TenantStatus


class TenantEntity:
    """
    Domain representation of a document.

    This object lives inside the business layer and is independent of
    FastAPI, SQLAlchemy, or Pydantic.
    """

    def __init__(
        self,
        *,
        tenant_id: UUID,
        organisation: str,
        created_at: datetime,
        updated_at: datetime,
        deleted_at: datetime | None = None,
        deleted_by: UUID | None = None,
        status: TenantStatus,
    ) -> None:
        # Identity
        self.tenant_id = tenant_id

        # Organisation
        self.organisation = organisation

        # Audit
        self.created_at = created_at
        self.updated_at = updated_at
        self.deleted_at = deleted_at
        self.deleted_by = deleted_by
        self.status = status

    def mark_activated(self) -> None:
        self.status = TenantStatus.ACTIVE
        self.updated_at = datetime.now(UTC)

    def mark_updated(self) -> None:
        self.updated_at = datetime.now(UTC)

    def mark_deleted(self, user_id: UUID) -> None:
        self.status = TenantStatus.SUSPENDED
        self.deleted_at = datetime.now(UTC)
        self.deleted_by = user_id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TenantEntity):
            return NotImplemented
        return self.tenant_id == other.tenant_id

    def __hash__(self) -> int:
        return hash(self.tenant_id)

    def __repr__(self) -> str:
        return (
            f"Tenant(tenant_id={self.tenant_id!r}, organisation={self.organisation!r})"
        )
