from datetime import datetime
import typing
import uuid
from sqlalchemy import (
    DateTime,
    UUID,
    Enum,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.postgres.models.base import Base
from src.shared.enums import TenantStatus

if typing.TYPE_CHECKING:
    from .user import User
    from .document import Document


class Tenant(Base):
    __tablename__ = "tenant"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        primary_key=True,
        server_default=text("gen_random_uuid()"),  # server-side responsiblity
    )

    # Relationships
    documents: Mapped[list["Document"] | None] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    employees: Mapped[list["User"] | None] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    # Company details
    organisation: Mapped[str] = mapped_column(String(255), nullable=False)

    # Status information
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, native_enum=True), default=TenantStatus.CREATED
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
    __table_args__ = (
        Index(
            "idx_tenants_organisation",
            "organisation",
        ),
        Index(
            "idx_tenants_created",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"Tenant(tenant_id={self.tenant_id!r}, organisation={self.organisation!r})"
        )
