from typing import Protocol
from uuid import UUID

from src.domain.ingestions.entities import IngestionJobEntity


class IngestionJobRepository(Protocol):
    """The repository layer handles all CRUD requests against a databse."""

    async def create(
        self,
        job: IngestionJobEntity,
    ) -> IngestionJobEntity: ...

    async def get_one(self, job_id: UUID, document_id: UUID) -> IngestionJobEntity: ...

    async def update(
        self,
        job: IngestionJobEntity,
    ) -> IngestionJobEntity: ...

    async def delete(
        self,
        job: IngestionJobEntity,
    ) -> None: ...
