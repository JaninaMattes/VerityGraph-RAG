from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.ingestions.entities import IngestionJobEntity
from src.domain.ingestions.repository import IngestionJobRepository
from src.infrastructure.database.postgres.mapper.ingestionjob import (
    IngestionJobMapper,
)
from src.infrastructure.database.postgres.models.ingestionjob import IngestionJob
from src.libs.core.logger import get_logger
from src.libs.exceptions.exceptions import (
    DatabaseInternalException,
    DatabaseOperationException,
    IngestionJobNotFoundException,
)

logger = get_logger("api.infra.postgres.ingestion")


class PostgresIngestionJobRepository(IngestionJobRepository):
    def __init__(
        self,
        session: AsyncSession,
    ):
        self._session = session

    async def create(
        self, job: IngestionJobEntity, idempotency_key: str
    ) -> IngestionJobEntity:
        db_job = IngestionJobMapper.to_model(job)
        # Add new object to session
        try:
            self._session.add(db_job)
        except IntegrityError as exc:
            logger.warning(
                "Database error as new job %s exists already: %s",
                job.job_id,
                exc,
            )
            raise DatabaseOperationException(
                f"Job '{job.job_id}' already exists in database."
            ) from exc
        except SQLAlchemyError as exc:
            logger.warning("Database error creating new job %s: %s", job.job_id, exc)
            raise DatabaseInternalException(
                f"Failed to create new ingestion job metadata entry for '{db_job.job_id}' in database."
            ) from exc

        return IngestionJobMapper.to_entity(db_job)  # after refresh

    async def update(
        self, job: IngestionJobEntity, idempotency_key: str
    ) -> IngestionJobEntity:

        try:
            current_db_job = await self._session.get(IngestionJob, job.job_id)
            if current_db_job is None or current_db_job.document_id != job.document_id:
                raise IngestionJobNotFoundException(job_id=job.job_id)  # Hide details

            # Merge objects
            db_job = IngestionJobMapper.to_model(job)
            merged_job = await self._session.merge(db_job)
            await self._session.refresh(merged_job)
        except SQLAlchemyError as exc:
            logger.warning("Database error updating job %s: %s", job.job_id, exc)
            raise DatabaseInternalException(
                f"Failed to update ingestion job metadata with ID '{job.job_id}'."
            ) from exc

        return IngestionJobMapper.to_entity(merged_job)

    async def delete(self, job_id: UUID, document_id: UUID) -> None:

        try:
            stmt = delete(IngestionJob).where(
                IngestionJob.job_id == job_id, IngestionJob.document_id == document_id
            )
            result = await self._session.execute(stmt)

            if result.scalar_one_or_none() is None:
                logger.exception("Ingestion job %s could not be found.", job_id)
                raise IngestionJobNotFoundException(job_id)

        except SQLAlchemyError as exc:
            logger.warning(
                "Database error while deleting job %s for document %s: %s",
                job_id,
                document_id,
                exc,
            )
            raise DatabaseInternalException(
                f"Failed to remove ingestion job '{job_id}' from database."
            ) from exc

    async def get_one(self, job_id: UUID, document_id: UUID) -> IngestionJobEntity:
        """Retrieve a record by its primary key."""
        try:
            stmt = select(IngestionJob).where(
                IngestionJob.job_id == job_id, IngestionJob.document_id == document_id
            )
            result = await self._session.execute(stmt)
            db_job = result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            logger.warning("Database error fetching job %s: %s", job_id, exc)
            raise DatabaseInternalException(
                f"Failed to read ingestion job metadata for '{job_id}' in database."
            ) from exc

        # Enforce ownership boundaries
        if db_job is None or db_job.job_id != job_id:
            logger.exception("Ingestion job %s could not be found.", job_id)
            raise IngestionJobNotFoundException(job_id=job_id)  # mask existence
        return IngestionJobMapper.to_entity(db_job)
