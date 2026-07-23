from abc import abstractmethod
from typing import Protocol
from uuid import UUID

from src.domain.users.entities import UserEntity


class UserRepository(Protocol):
    """The repository layer handles all CRUD requests against a databse."""

    @abstractmethod
    async def create(
        self,
        user: UserEntity,
    ) -> UserEntity: ...

    @abstractmethod
    async def update(
        self,
        user: UserEntity,
    ) -> UserEntity: ...

    @abstractmethod
    async def get(self, user_id: UUID) -> UserEntity: ...

    @abstractmethod
    async def delete(
        self,
        user: UserEntity,
    ) -> UserEntity: ...
