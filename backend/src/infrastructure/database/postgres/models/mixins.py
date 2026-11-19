"""Audit columns that several tables share.

The application sets the timestamps (so the values are known without a refresh in
async code); the server default covers rows that other tools insert.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import UUID, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    """Return the current time in UTC."""
    return datetime.now(UTC)


class CreatedAtMixin:
    """For rows that never change after the insert."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )


class TimestampMixin(CreatedAtMixin):
    """For rows that change: `updated_at` moves on every ORM update."""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )


class SoftDeleteMixin:
    """For rows that are marked as deleted instead of being removed."""

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(UUID)
