from dataclasses import dataclass
from uuid import UUID

from src.shared.enums.ingestionjob import IngestionStage, ProcessingStatus


@dataclass(slots=True, frozen=True)
class IngestionJob:
    """
    Domain representation of a new job object.
    """

    document_id: UUID
    workflow_run_id: str


@dataclass(slots=True, frozen=True)
class IngestionJobResponse:
    """
    Domain representation of a new job object.
    """

    job_id: UUID
    document_id: UUID
    current_stage: IngestionStage | None
    status: ProcessingStatus


@dataclass(slots=True, frozen=True)
class CurrentIngestionJob:
    """
    Domain representation of a job object.
    """

    job_id: UUID
    document_id: UUID
    current_stage: IngestionStage | None
    status: ProcessingStatus
