from typing import Protocol
from uuid import UUID

from src.domain.ingestions.entities import IngestionJobEntity


class IngestionJobRepository(Protocol):
    """Persistence port for ingestion jobs. Implementations flush but never commit."""

    async def create(self, job: IngestionJobEntity) -> IngestionJobEntity:
        """Insert the job, or overwrite it if it exists (safe for retries)."""
        raise NotImplementedError

    async def update(self, job: IngestionJobEntity) -> IngestionJobEntity:
        """Save the changed job."""
        raise NotImplementedError

    async def delete(self, job_id: UUID, document_id: UUID) -> None:
        """Delete the job. Raise IngestionJobNotFoundException if it does not exist."""
        raise NotImplementedError

    async def get_one(self, job_id: UUID, document_id: UUID) -> IngestionJobEntity:
        """Return the job. Raise IngestionJobNotFoundException if it does not exist."""
        raise NotImplementedError
