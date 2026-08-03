import uuid
from datetime import UTC, datetime
from uuid import UUID

from src.domain.ingestions.dataclasses import (
    CurrentIngestionJob,
    IngestionJob,
    IngestionJobResponse,
)
from src.domain.ingestions.entities import IngestionJobEntity
from src.domain.ingestions.repository import IngestionJobRepository
from src.shared.core.logger import get_logger
from src.shared.enums.ingestionjob import ProcessingStatus
from src.shared.exception.exceptions import (
    DatabaseException,
    JobServiceException,
    NotFoundException,
)

logger = get_logger("api.infra.postgres.jobs")


class IngestionService:
    """The service layer defines the business logic that ineracts with the repository."""

    def __init__(
        self,
        repository: IngestionJobRepository,
    ) -> None:
        self.repository = repository

    async def create(
        self, job: IngestionJob, document_id: uuid.UUID
    ) -> IngestionJobResponse:
        # Randomly generate new UUID
        job_id = uuid.uuid4()

        now = datetime.now(UTC)
        entity = IngestionJobEntity(
            job_id=job_id,
            document_id=document_id,
            workflow_run_id=job.workflow_run_id,
            status=ProcessingStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        try:
            db_job = await self.repository.create(entity)
            return IngestionJobResponse(
                job_id=db_job.job_id,
                document_id=db_job.document_id,
                current_stage=db_job.current_stage,
                status=db_job.status,
            )
        except DatabaseException:
            raise
        except Exception as exc:
            logger.warning(
                "Unexpected error occured when creating new ingestion job %s for document %s: %s",
                job_id,
                document_id,
                exc,
            )
            raise JobServiceException(
                "Failed to store new ingestion job metadata.",
            ) from exc

    async def get(self, job_id: uuid.UUID, document_id: UUID) -> CurrentIngestionJob:
        try:
            db_job = await self.repository.get_one(job_id, document_id)

            return CurrentIngestionJob(
                job_id=db_job.job_id,
                document_id=db_job.document_id,
                current_stage=db_job.current_stage,
                status=db_job.status,
            )

        except DatabaseException:
            raise
        except NotFoundException:
            raise
        except Exception as exc:
            logger.warning(
                "Unexpected error occured when searching for ingestion job %s for document %s: %s",
                job_id,
                document_id,
                exc,
            )
            raise JobServiceException(
                "Failed to find ingestion job.",
            ) from exc
