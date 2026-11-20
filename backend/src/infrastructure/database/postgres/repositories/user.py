from uuid import UUID, uuid4

from sqlalchemy import delete, select

from src.domain.users.entities import UserEntity
from src.domain.users.repository import UserRepository
from src.infrastructure.database.postgres.mapper.user import UserMapper
from src.infrastructure.database.postgres.models.credentials import UserCredentials
from src.infrastructure.database.postgres.models.user import User
from src.infrastructure.database.postgres.repositories.base import (
    PostgresRepository,
    translate_db_errors,
)
from src.libs.enums.credentials import CredentialStatus
from src.libs.enums.user import UserStatus
from src.libs.exceptions.exceptions import UserNotFoundException

# The provider name of a password stored by this application.
LOCAL_PROVIDER = "local"


class PostgresUserRepository(PostgresRepository, UserRepository):
    """Users in PostgreSQL. Every query is scoped to one tenant."""

    async def create(
        self, user: UserEntity, password_hash: str | None = None
    ) -> UserEntity:
        """Insert the user and its local credential, if a password hash is given.

        A duplicate email in the tenant raises ConflictException.
        """
        model = UserMapper.to_model(user)
        if password_hash is not None:
            model.credentials.append(
                UserCredentials(
                    credentials_id=uuid4(),
                    provider=LOCAL_PROVIDER,
                    password_hash=password_hash,
                    status=CredentialStatus.VALID,
                )
            )
        return UserMapper.to_entity(await self._add(model))

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

    async def find_login_candidates(self, email: str) -> list[tuple[UserEntity, str]]:
        """Return the users with this email in any tenant and their password hash.

        Only users that are not disabled or deleted and have a usable local
        credential are returned.
        """
        statement = (
            select(User, UserCredentials.password_hash)
            .join(UserCredentials, UserCredentials.user_id == User.user_id)
            .where(
                User.email == email,
                User.status != UserStatus.DISABLED,
                User.deleted_at.is_(None),
                UserCredentials.provider == LOCAL_PROVIDER,
                UserCredentials.status != CredentialStatus.REVOKED,
                UserCredentials.deleted_at.is_(None),
                UserCredentials.password_hash.is_not(None),
            )
        )
        with translate_db_errors("find login candidates"):
            rows = (await self._session.execute(statement)).all()
        return [
            (UserMapper.to_entity(user), password_hash)
            for user, password_hash in rows
            if password_hash  # the query excludes NULL; this narrows the type
        ]
