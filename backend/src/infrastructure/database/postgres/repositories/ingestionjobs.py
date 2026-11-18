from uuid import UUID

from sqlalchemy import delete, select

from src.domain.ingestions.entities import IngestionJobEntity
from src.domain.ingestions.repository import IngestionJobRepository
from src.infrastructure.database.postgres.mapper.ingestionjob import (
    IngestionJobMapper,
)
from src.infrastructure.database.postgres.models.ingestionjob import IngestionJob
from src.infrastructure.database.postgres.repositories.base import PostgresRepository
from src.libs.exceptions.exceptions import IngestionJobNotFoundException


class PostgresIngestionJobRepository(PostgresRepository, IngestionJobRepository):
    """Ingestion jobs in PostgreSQL. Every query is scoped to one document."""

    async def create(self, job: IngestionJobEntity) -> IngestionJobEntity:
        """Insert or overwrite the job, so a retried activity does not fail."""
        return IngestionJobMapper.to_entity(
            await self._merge(IngestionJobMapper.to_model(job))
        )

    async def update(self, job: IngestionJobEntity) -> IngestionJobEntity:
        return IngestionJobMapper.to_entity(
            await self._merge(IngestionJobMapper.to_model(job))
        )

    async def delete(self, job_id: UUID, document_id: UUID) -> None:
        await self._delete_one(
            delete(IngestionJob).where(
                IngestionJob.job_id == job_id, IngestionJob.document_id == document_id
            ),
            IngestionJobNotFoundException(job_id),
        )

    async def get_one(self, job_id: UUID, document_id: UUID) -> IngestionJobEntity:
        row = await self._scalar_one(
            select(IngestionJob).where(
                IngestionJob.job_id == job_id, IngestionJob.document_id == document_id
            ),
            IngestionJobNotFoundException(job_id),
        )
        return IngestionJobMapper.to_entity(row)
