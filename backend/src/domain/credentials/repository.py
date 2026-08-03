from typing import Protocol
from uuid import UUID

from src.domain.credentials.entities import CredentialsEntity


class CredentialsRepository(Protocol):
    """The repository layer handles all CRUD requests against a databse."""

    async def create(
        self,
        credentials: CredentialsEntity,
    ) -> CredentialsEntity: ...

    async def get_one(
        self, credentials_id: UUID, user_id: UUID
    ) -> CredentialsEntity: ...

    async def update(
        self,
        credentials: CredentialsEntity,
    ) -> CredentialsEntity: ...

    async def delete(
        self,
        credentials: CredentialsEntity,
    ) -> None: ...
