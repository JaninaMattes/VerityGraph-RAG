from typing import Protocol
from uuid import UUID

from src.domain.users.entities import UserEntity


class UserRepository(Protocol):
    """The repository layer handles all CRUD requests against a databse."""

    async def create(
        self,
        user: UserEntity,
    ) -> UserEntity:
        raise NotImplementedError("Subclasses must implement create method")

    async def update(
        self,
        user: UserEntity,
    ) -> UserEntity:
        raise NotImplementedError("Subclasses must implement update method")

    async def delete(self, user_id: UUID, tenant_id: UUID) -> None:
        raise NotImplementedError("Subclasses must implement delete method")

    async def get_one(self, user_id: UUID, tenant_id: UUID) -> UserEntity:
        raise NotImplementedError("Subclasses must implement get_one method")