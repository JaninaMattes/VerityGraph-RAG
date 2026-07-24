import typing
import uuid
from datetime import datetime

from sqlalchemy import UUID, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.postgres.models.base import Base

if typing.TYPE_CHECKING:
    from .user import User


class Session(Base):
    __tablename__ = "session"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        primary_key=True,
        # server_default=text("gen_random_uuid()"),  # server-side responsiblity
    )
    # Foreign key
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE")
    )

    # Relationship
    user: Mapped[User] = relationship(back_populates="user_sessions")

    # Auth
    ip_address: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(
        Text, unique=True, index=True, nullable=False
    )

    # Audit information
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "idx_sessions_user",
            "user_id",
        ),
        Index(
            "idx_session_created",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return f"Session(session_id={self.session_id!r})"
