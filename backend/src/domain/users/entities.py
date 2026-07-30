from datetime import UTC, datetime
from uuid import UUID

from src.shared.enums import UserRole, UserStatus


class UserEntity:
    """
    Domain representation of a user.

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
        roles: list[UserRole],
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
        self.roles = roles

        # Audit
        self.created_at = created_at
        self.updated_at = updated_at
        self.deleted_at = deleted_at
        self.deleted_by = deleted_by
        self.status = status

    def mark_activated(self) -> None:
        self.status = UserStatus.ACTIVE
        self.updated_at = datetime.now(UTC)

    def mark_updated(self) -> None:
        self.updated_at = datetime.now(UTC)

    def mark_deleted(self, tenant_id: UUID) -> None:
        self.status = UserStatus.DISABLED
        self.deleted_at = datetime.now(UTC)
        self.deleted_by = tenant_id

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, UserEntity):
            return NotImplemented
        return self.user_id == other.user_id

    def __hash__(self) -> int:
        return hash(self.user_id)

    def __repr__(self) -> str:
        return f"User(user_id={self.user_id!r}, username={self.username!r}, email={self.email!r})"
