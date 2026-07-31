# import typing
import uuid
from datetime import UTC, datetime

from sqlalchemy import UUID, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.postgres.base import Base
from src.infrastructure.database.postgres.models.document import Document
from src.infrastructure.database.postgres.models.user import User
from src.shared.enums import TenantStatus


class Tenant(Base):
    __tablename__ = "tenant"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        primary_key=True,
        index=True,
        # server_default=text("gen_random_uuid()"),  # server-side responsiblity
    )
    # Relationships
    documents: Mapped[list[Document] | None] = relationship(back_populates="tenant")
    users: Mapped[list[User] | None] = relationship(back_populates="tenant")

    # Company details
    organisation: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[TenantStatus] = mapped_column(
        Enum(TenantStatus, name="tenantstatus", native_enum=True),
        default=TenantStatus.CREATED,
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

    # __table_args__ = (
    #     Index(
    #         "idx_tenants_organisation",
    #         "organisation",
    #     ),
    #     Index(
    #         "idx_tenants_created",
    #         "created_at",
    #     ),
    # )

    def __repr__(self) -> str:
        return f"Tenant(tenant_id={self.tenant_id!r})"
