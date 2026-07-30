import typing
import uuid
from datetime import datetime

from sqlalchemy import UUID, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.postgres.base import Base
from src.shared.enums import CredentialStatus

if typing.TYPE_CHECKING:
    from .user import User


class UserCredentials(Base):
    __tablename__ = "credentials"

    credentials_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        primary_key=True,
        # server_default=text("gen_random_uuid()"),  # server-side responsiblity
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE")
    )

    # Relationship
    user: Mapped["User"] = relationship(back_populates="credentials")

    # Auth
    provider: Mapped[str] = mapped_column(
        String(255)
    )  # e.g. Local, or Google credentials
    password_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[CredentialStatus] = mapped_column(
        Enum(CredentialStatus, name="credentialstatus", native_enum=True),
        default=CredentialStatus.CREATED,
    )

    # Audit information
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(UUID)

    # __table_args__ = (
    #     Index(
    #         "idx_credentials_user",
    #         "user_id",
    #     ),
    #     Index(
    #         "idx_credentials_created",
    #         "created_at",
    #     ),
    # )

    def __repr__(self) -> str:
        return f"Credentials(credentials_id={self.credentials_id!r})"
