import typing
import uuid
from datetime import datetime

from sqlalchemy import (
    UUID,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.postgres.base import Base
from src.infrastructure.database.postgres.models.mixins import (
    SoftDeleteMixin,
    TimestampMixin,
)
from src.libs.enums.credentials import CredentialStatus

if typing.TYPE_CHECKING:
    from .user import User


class UserCredentials(TimestampMixin, SoftDeleteMixin, Base):
    """One login method of a user (for example a local password or Google)."""

    __tablename__ = "credentials"

    credentials_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"),
        index=True,
    )

    # Relationship
    user: Mapped[User] = relationship(back_populates="credentials")

    # Credentials properties
    provider: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str | None] = mapped_column(Text)
    status: Mapped[CredentialStatus] = mapped_column(
        Enum(CredentialStatus, name="credentialstatus", native_enum=True),
        default=CredentialStatus.CREATED,
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_provider"),
        Index("ix_credentials_provider", "provider"),
        Index("ix_credentials_status", "status"),
        Index("ix_credentials_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"UserCredentials("
            f"credentials_id={self.credentials_id!r}, "
            f"provider={self.provider!r}, "
            f"status={self.status!r}"
            ")"
        )
