from typing import Protocol
from uuid import UUID

from src.domain.ingestions.entities import IngestionJobEntity


class IngestionJobRepository(Protocol):
    """The repository layer handles all CRUD requests against a databse."""

    async def create(
        self,
        job: IngestionJobEntity,
    ) -> IngestionJobEntity:
        raise NotImplementedError("Subclasses must implement create method")

    async def get_one(self, job_id: UUID, document_id: UUID) -> IngestionJobEntity:
        raise NotImplementedError("Subclasses must implement get_one method")

    async def update(
        self,
        job: IngestionJobEntity,
    ) -> IngestionJobEntity:
        raise NotImplementedError("Subclasses must implement update method")

    async def delete(
        self,
        job: IngestionJobEntity,
    ) -> None:
        raise NotImplementedError("Subclasses must implement delete method")
