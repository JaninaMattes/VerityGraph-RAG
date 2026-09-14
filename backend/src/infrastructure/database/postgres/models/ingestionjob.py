import typing
import uuid
from datetime import UTC, datetime

from sqlalchemy import UUID, BigInteger, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.postgres.base import Base
from src.shared.enums.ingestionjob import IngestionStage, ProcessingStatus

if typing.TYPE_CHECKING:
    from .document import Document


class IngestionJob(Base):
    __tablename__ = "ingestion_job"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        primary_key=True,
        index=True,
        # server_default=text("gen_random_uuid()"),  # server-side responsiblity
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document.document_id", ondelete="CASCADE"),
        index=True,
    )

    # Relationship
    document: Mapped[Document] = relationship(back_populates="ingestion_jobs")

    # Properties
    workflow_id: Mapped[str | None] = mapped_column(String(255))
    workflow_run_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    current_stage: Mapped[IngestionStage | None] = mapped_column(
        Enum(
            IngestionStage,
            name="ingestionstage",
            native_enum=True,
        )
    )
    status: Mapped[ProcessingStatus] = mapped_column(
        Enum(
            ProcessingStatus,
            name="processingstatus",
            native_enum=True,
        ),
        default=ProcessingStatus.PENDING,
    )
    attempt_count: Mapped[int] = mapped_column(
        BigInteger, default=0, server_default="0"
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, typing.Any] | None] = mapped_column(
        JSONB, default=None
    )  # For state/error tracking

    # Audit information
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "ix_job_workflow_id",
            "workflow_id",
        ),
        Index(
            "ix_job_workflow_run_id",
            "workflow_run_id",
        ),
        Index(
            "ix_job_attempt_count",
            "attempt_count",
        ),
        Index(
            "ix_job_stage",
            "current_stage",
        ),
        Index(
            "ix_job_status",
            "status",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"IngestionJob("
            f"job_id={self.job_id!r}, "
            f"workflow_id={self.workflow_id!r}, "
            f"workflow_run_id={self.workflow_run_id!r}, "
            f"status={self.status!r}"
            ")"
        )
