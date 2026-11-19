import typing
import uuid

from sqlalchemy import (
    ARRAY,
    UUID,
    Enum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.postgres.base import Base
from src.infrastructure.database.postgres.models.credentials import UserCredentials
from src.infrastructure.database.postgres.models.mixins import (
    SoftDeleteMixin,
    TimestampMixin,
)
from src.libs.enums.user import UserRole, UserStatus

if typing.TYPE_CHECKING:
    from .tenant import Tenant  # noqa: TC004

class User(TimestampMixin, SoftDeleteMixin, Base):
    """A user of one tenant. The email address is unique within the tenant."""

    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        index=True,
    )

    # Relationship
    tenant: Mapped[Tenant] = relationship(back_populates="users")
    credentials: Mapped[list[UserCredentials]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # User properties
    username: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    roles: Mapped[list[UserRole]] = mapped_column(
        ARRAY(Enum(UserRole, name="userrole", native_enum=True)),
        default=lambda: [UserRole.USER],
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="userstatus", native_enum=True),
        default=UserStatus.CREATED,
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
        # Login looks a user up by email before the tenant is known.
        Index("ix_user_email", "email"),
        Index("ix_user_status", "status"),
        Index("ix_user_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"User("
            f"user_id={self.user_id!r}, "
            f"username={self.username!r}, "
            f"email={self.email!r}, "
            f"status={self.status!r}"
            ")"
        )
