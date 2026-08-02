# import typing
import typing
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    ARRAY,
    UUID,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.postgres.base import Base
from src.infrastructure.database.postgres.models.credentials import UserCredentials
from src.shared.enums import UserRole, UserStatus

if typing.TYPE_CHECKING:
    from .tenant import Tenant  # noqa: TC004


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        primary_key=True,
        index=True,
        # server_default=text("gen_random_uuid()"),  # server-side responsiblity
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        index=True,
    )

    # Relationship
    tenant: Mapped[Tenant] = relationship(back_populates="users")
    credentials: Mapped[list[UserCredentials]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )

    # User details
    username: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    roles: Mapped[list[UserRole]] = mapped_column(
        ARRAY(Enum(UserRole, name="userrole", native_enum=True)),
        default=lambda: [UserRole.USER],
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="userstatus", native_enum=True),
        default=UserStatus.CREATED,
    )

    # Audit information
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(UUID)

    __table_args__ = (
        Index(
            "ix_user_created_at",
            "created_at",
        ),
        Index(
            "ix_user_status",
            "status",
        ),
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
