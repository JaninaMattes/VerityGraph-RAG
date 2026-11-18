"""User use cases. Every operation is scoped to one tenant."""

import uuid
from datetime import UTC, datetime

from src.domain.users.dataclasses import UpdateUser, User
from src.domain.users.entities import UserEntity
from src.domain.users.repository import UserRepository
from src.libs.enums.user import UserRole, UserStatus


class UserService:
    """Creates, reads, updates and deletes users of a tenant.

    Repository errors (NotFoundException, DatabaseException) propagate unchanged.
    """

    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    async def create(self, user: User, tenant_id: uuid.UUID) -> UserEntity:
        """Store a new user with role USER and status CREATED and return it."""
        now = datetime.now(UTC)
        entity = UserEntity(
            user_id=uuid.uuid4(),
            tenant_id=tenant_id,
            username=user.username,
            email=user.email,
            roles=[UserRole.USER],
            status=UserStatus.CREATED,
            created_at=now,
            updated_at=now,
        )
        return await self.user_repository.create(entity)

    async def get(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> UserEntity:
        """Return the user. Raise UserNotFoundException if the tenant has no such user."""
        return await self.user_repository.get_one(user_id, tenant_id)

    async def update(self, user: UpdateUser) -> UserEntity:
        """Change the username and email and return the user."""
        entity = await self.user_repository.get_one(user.user_id, user.tenant_id)
        entity.username = user.username
        entity.email = user.email
        entity.mark_updated()
        return await self.user_repository.update(entity)

    async def delete(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        """Delete the user. Raise UserNotFoundException if the tenant has no such user."""
        await self.user_repository.delete(user_id, tenant_id)
