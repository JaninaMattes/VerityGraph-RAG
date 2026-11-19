"""User use cases. Every operation is scoped to one tenant."""

import asyncio
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from src.domain.auth.hasher import PasswordHasher
from src.domain.users.dataclasses import UpdateUser, User
from src.domain.users.entities import UserEntity
from src.domain.users.repository import UserRepository
from src.libs.enums.user import UserRole, UserStatus


class UserService:
    """Creates, reads, updates and deletes users of a tenant.

    Repository errors (NotFoundException, DatabaseException) propagate unchanged.
    """

    def __init__(self, user_repository: UserRepository, hasher: PasswordHasher) -> None:
        self.user_repository = user_repository
        self.hasher = hasher

    async def create(
        self,
        user: User,
        tenant_id: uuid.UUID,
        roles: Iterable[UserRole] = (UserRole.USER,),
    ) -> UserEntity:
        """Store a new user with status CREATED and the password's hash; return it.

        Hashing runs in a thread because Argon2 blocks for tens of milliseconds.
        """
        now = datetime.now(UTC)
        entity = UserEntity(
            user_id=uuid.uuid4(),
            tenant_id=tenant_id,
            username=user.username,
            email=user.email,
            roles=list(roles),
            status=UserStatus.CREATED,
            created_at=now,
            updated_at=now,
        )
        password_hash = await asyncio.to_thread(self.hasher.hash, user.password)
        return await self.user_repository.create(entity, password_hash)

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
