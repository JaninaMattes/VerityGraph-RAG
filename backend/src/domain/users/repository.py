from typing import Protocol
from uuid import UUID

from src.domain.users.entities import UserEntity


class UserRepository(Protocol):
    """The repository layer handles all CRUD requests against a databse."""

    async def create(
        self,
        user: UserEntity,
    ) -> UserEntity: ...

    async def update(
        self,
        user: UserEntity,
    ) -> UserEntity: ...

    async def get(self, user_id: UUID) -> UserEntity: ...

    async def delete(
        self,
        user: UserEntity,
    ) -> UserEntity: ...
