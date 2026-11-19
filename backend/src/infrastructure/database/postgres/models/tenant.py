import uuid

from sqlalchemy import UUID, Enum, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.postgres.base import Base
from src.infrastructure.database.postgres.models.document import Document
from src.infrastructure.database.postgres.models.mixins import (
    SoftDeleteMixin,
    TimestampMixin,
)
from src.infrastructure.database.postgres.models.user import User
from src.libs.enums.tenant import TenantStatus


class Tenant(TimestampMixin, SoftDeleteMixin, Base):
    """An organisation. Every other row belongs to exactly one tenant."""

    __tablename__ = "tenant"

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)

    # Relationships
    documents: Mapped[list[Document] | None] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    users: Mapped[list[User] | None] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    # Company details
    organisation: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenantstatus", native_enum=True),
        default=TenantStatus.CREATED,
    )

    __table_args__ = (
        Index("ix_tenant_organisation", "organisation"),
        Index("ix_tenant_status", "status"),
        Index("ix_tenant_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"Tenant("
            f"tenant_id={self.tenant_id!r}, "
            f"organisation={self.organisation!r}, "
            f"status={self.status!r}"
            ")"
        )
