import typing
import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    UUID,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.postgres.models.base import Base
from src.shared.enums import UserRole, UserStatus

if typing.TYPE_CHECKING:
    from .credentials import UserCredentials
    from .session import Session
    from .tenant import Tenant


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        primary_key=True,
        # server_default=text("gen_random_uuid()"),  # server-side responsiblity
    )
    # Foreign key
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenant.tenant_id", ondelete="CASCADE")
    )

    # Relationship
    tenant: Mapped[Tenant] = relationship(back_populates="users")
    user_credentials: Mapped[list[UserCredentials]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    user_sessions: Mapped[list[Session]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    # User details
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # index preserves data integrity

    roles: Mapped[list[UserRole]] = mapped_column(
        ARRAY(Enum(UserRole, native_enum=True)), server_default="{user}"
    )

    # Status information
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, native_enum=True), default=UserStatus.CREATED
    )

    # Audit information
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(UUID)

    __table_args__ = (
        Index(
            "idx_users_tenant",
            "tenant_id",
        ),
        Index(
            "idx_users_created",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return f"User(user_id={self.user_id!r}, username={self.username!r}, user_email={self.email!r})"
