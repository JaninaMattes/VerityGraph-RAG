"""Authentication use cases: log in with a password, resolve a token's user."""

import asyncio
from uuid import UUID

from src.domain.auth.entities import Principal
from src.domain.auth.hasher import PasswordHasher
from src.domain.users.entities import UserEntity
from src.domain.users.repository import UserRepository
from src.libs.enums.user import UserStatus
from src.libs.exceptions.exceptions import (
    AuthenticationException,
    UserNotFoundException,
)


def _principal(user: UserEntity) -> Principal:
    return Principal(user.user_id, user.tenant_id, frozenset(user.roles))


class AuthService:
    """Checks credentials. Every failure raises the same AuthenticationException."""

    def __init__(self, user_repository: UserRepository, hasher: PasswordHasher) -> None:
        self.user_repository = user_repository
        self.hasher = hasher

    async def authenticate(self, email: str, password: str) -> Principal:
        """Return the principal of the user with this email and password.

        An email can exist in several tenants; the password selects the user. Raise
        AuthenticationException if no user or more than one user matches. Emails
        are stored in lower case, so the given email is trimmed and lower-cased.
        Hashing runs in a thread because Argon2 blocks for tens of milliseconds.
        """
        email = email.strip().lower()
        candidates = await self.user_repository.find_login_candidates(email)
        if not candidates:
            await asyncio.to_thread(self.hasher.verify, password, None)
            raise AuthenticationException("Unknown email.")
        matches = [
            user
            for user, password_hash in candidates
            if await asyncio.to_thread(self.hasher.verify, password, password_hash)
        ]
        if len(matches) != 1:
            raise AuthenticationException(f"{len(matches)} users match the password.")
        return _principal(matches[0])

    async def resolve(self, user_id: UUID, tenant_id: UUID) -> Principal:
        """Return the principal of a verified token's user with its current roles.

        Raise AuthenticationException if the user no longer exists, is disabled or
        is deleted, so a token stops working at once.
        """
        try:
            user = await self.user_repository.get_one(user_id, tenant_id)
        except UserNotFoundException:
            raise AuthenticationException(f"User {user_id} does not exist.") from None
        if user.status is UserStatus.DISABLED or user.deleted_at is not None:
            raise AuthenticationException(f"User {user_id} is disabled.")
        return _principal(user)
