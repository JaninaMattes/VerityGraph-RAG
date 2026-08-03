from datetime import UTC, datetime
from uuid import UUID

from src.shared.enums.ingestionjob import IngestionStage, ProcessingStatus


class IngestionJobEntity:
    """
    Domain representation of an ingestion job.

    This object lives inside the business layer and is independent of
    FastAPI, SQLAlchemy, or Pydantic.
    """

    def __init__(
        self,
        *,
        job_id: UUID,
        document_id: UUID,
        workflow_id: str | None = None,
        workflow_run_id: str,
        current_stage: IngestionStage | None = None,
        status: ProcessingStatus,
        attempt_count: int = 0,
        error_message: str | None = None,
        created_at: datetime,
        updated_at: datetime,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        # Identity
        self.job_id = job_id
        self.document_id = document_id
        self.workflow_id = workflow_id
        self.workflow_run_id = workflow_run_id

        # Other job properties
        self.current_stage = current_stage
        self.status = status
        self.attempt_count = attempt_count
        self.error_message = error_message

        # Audit
        self.created_at = created_at
        self.updated_at = updated_at
        self.started_at = started_at
        self.finished_at = finished_at

        def mark_completed(self) -> None:
            self.status = ProcessingStatus.COMPLETED
            self.current_stage = None
            self.updated_at = datetime.now(UTC)
