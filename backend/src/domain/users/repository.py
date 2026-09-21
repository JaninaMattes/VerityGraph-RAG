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

    async def get_one(self, user_id: UUID) -> UserEntity:
        raise NotImplementedError("Subclasses must implement get_one method")

    async def update(
        self,
        user: UserEntity,
    ) -> UserEntity:
        raise NotImplementedError("Subclasses must implement update method")

    async def delete(
        self,
        user: UserEntity,
    ) -> None:
        raise NotImplementedError("Subclasses must implement delete method")
