from uuid import UUID

from sqlalchemy import delete, select

from src.domain.users.entities import UserEntity
from src.domain.users.repository import UserRepository
from src.infrastructure.database.postgres.mapper.user import UserMapper
from src.infrastructure.database.postgres.models.user import User
from src.infrastructure.database.postgres.repositories.base import PostgresRepository
from src.libs.exceptions.exceptions import UserNotFoundException


class PostgresUserRepository(PostgresRepository, UserRepository):
    """Users in PostgreSQL. Every query is scoped to one tenant."""

    async def create(self, user: UserEntity) -> UserEntity:
        """Insert the user. A duplicate email raises DatabaseOperationException."""
        return UserMapper.to_entity(await self._add(UserMapper.to_model(user)))

    async def update(self, user: UserEntity) -> UserEntity:
        return UserMapper.to_entity(await self._merge(UserMapper.to_model(user)))

    async def delete(self, user_id: UUID, tenant_id: UUID) -> None:
        await self._delete_one(
            delete(User).where(User.user_id == user_id, User.tenant_id == tenant_id),
            UserNotFoundException(user_id),
        )

    async def get_one(self, user_id: UUID, tenant_id: UUID) -> UserEntity:
        row = await self._scalar_one(
            select(User).where(User.user_id == user_id, User.tenant_id == tenant_id),
            UserNotFoundException(user_id),
        )
        return UserMapper.to_entity(row)
