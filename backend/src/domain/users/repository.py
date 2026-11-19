from typing import Protocol
from uuid import UUID

from src.domain.users.entities import UserEntity


class UserRepository(Protocol):
    """The repository layer handles all CRUD requests against a databse."""

    async def create(
        self, user: UserEntity, password_hash: str | None = None
    ) -> UserEntity:
        """Store the user and, if given, its local password hash."""
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

    async def find_login_candidates(self, email: str) -> list[tuple[UserEntity, str]]:
        """Return the enabled users with this email in any tenant, with their hash."""
        raise NotImplementedError("Subclasses must implement find_login_candidates")
