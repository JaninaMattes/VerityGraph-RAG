from datetime import datetime
import typing
import uuid

from sqlalchemy import UUID, DateTime, Enum, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.postgres.models.base import Base
from src.shared.enums import CredentialStatus

if typing.TYPE_CHECKING:
    from .user import User


class UserCredentials(Base):
    __tablename__ = "credentials"

    credentials_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        primary_key=True,
        server_default=text("gen_random_uuid()"),  # server-side responsiblity
    )
    # Foreign key
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.user_id"))

    provider: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # e.g. Local, or Google credentials

    # Relationship
    user: Mapped["User"] = relationship(back_populates="user_credentials")

    # Auth
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)

    # Status information
    status: Mapped[CredentialStatus] = mapped_column(
        Enum(CredentialStatus, native_enum=True), default=CredentialStatus.INVALID
    )

    # Audit information
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, server_default=None
    )
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID,
        default=None,
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, server_default=None
    )  # security audit

    __table_args__ = (
        Index(
            "idx_credentials_user",
            "user_id",
        ),
        Index(
            "idx_credentials_created",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return f"Credentials(user_id={self.user_id!r})"
