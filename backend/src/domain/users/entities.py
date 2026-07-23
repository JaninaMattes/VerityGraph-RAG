from datetime import datetime, timezone
from uuid import UUID

from src.shared.enums import UserStatus


class UserEntity:
    """
    Domain representation of a document.

    This object lives inside the business layer and is independent of
    FastAPI, SQLAlchemy, or Pydantic.
    """

    def __init__(
        self,
        *,
        user_id: UUID,
        tenant_id: UUID,
        username: str,
        email: str,
        created_at: datetime,
        updated_at: datetime,
        deleted_at: datetime | None = None,
        deleted_by: UUID | None = None,
        status: UserStatus,
    ) -> None:
        # Identity
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.username = username
        self.email = email

        # Audit
        self.created_at = created_at
        self.updated_at = updated_at
        self.deleted_at = deleted_at
        self.deleted_by = deleted_by
        self.status = status

    def mark_updated(self) -> None:
        self.status = UserStatus.UPDATED
        self.updated_at = datetime.now(timezone.utc)

    def mark_deleted(self, tenant_id: UUID) -> None:
        self.status = UserStatus.DELETED
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = tenant_id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UserEntity):
            return NotImplemented
        return self.user_id == other.user_id

    def __hash__(self) -> int:
        return hash(self.user_id)

    def __repr__(self) -> str:
        return f"User(user_id={self.user_id!r}, username={self.username!r}, email={self.email!r})"
