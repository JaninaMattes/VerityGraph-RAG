from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.users.entities import UserEntity
from src.domain.users.repository import UserRepository
from src.infrastructure.database.postgres.mapper.user import UserMapper
from src.infrastructure.database.postgres.models.user import User
from src.libs.core.logger import get_logger
from src.libs.exceptions.exceptions import (
    DatabaseInternalException,
    DatabaseOperationException,
    UserNotFoundException,
)

logger = get_logger("api.infra.postgres.user")


class PostgresUserRepository(UserRepository):
    def __init__(
        self,
        session: AsyncSession,
    ):
        self._session = session

    async def create(
        self,
        user: UserEntity,
    ) -> UserEntity:
        db_user = UserMapper.to_model(user)
        try:
            # Add new object to session
            self._session.add(db_user)
            await self._session.flush()
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            logger.error(
                "Database error as user %s exists already in the database.",
                user.user_id,
            )
            raise DatabaseOperationException(
                f"User '{db_user.user_id}' already exists in database."
            ) from exc

        except SQLAlchemyError as exc:
            await self._session.rollback()
            logger.error("Database error creating new user %s", user.user_id)
            raise DatabaseInternalException(
                f"Failed to create new user entry for '{db_user.user_id}' in database."
            ) from exc

        # Triggers lazy load / refresh
        return UserMapper.to_entity(db_user)  # after rerfesh

    async def update(
        self,
        user: UserEntity,
    ) -> UserEntity:
        db_user = UserMapper.to_model(user)

        # Merge objects
        try:
            merged_user = await self._session.merge(db_user)
            await self._session.flush()
            await self._session.commit()
        except SQLAlchemyError as exc:
            await self._session.rollback()
            logger.error("Database error updating user %s", user.user_id)

            raise DatabaseInternalException(
                f"Failed to update user '{db_user.user_id}'."
            ) from exc

        # Triggers lazy load / refresh
        return UserMapper.to_entity(merged_user)  # after refresh

    async def delete(self, user_id: UUID, tenant_id: UUID) -> None:

        try:
            stmt = delete(User).where(
                User.user_id == user_id, User.tenant_id == tenant_id
            )
            result = await self._session.execute(stmt)
            db_user = result.scalar_one_or_none()

            if db_user is None:
                logger.warning("User with id '%s' could not be found.", user_id)
                raise UserNotFoundException(user_id)

            # Flush or commit to push the change and catch database-level errors
            await self._session.flush()

        except SQLAlchemyError as exc:
            await self._session.rollback()
            logger.error(
                "Failed to remove document with id '%s' in database.",
                user_id,
            )
            raise DatabaseInternalException(
                f"Failed to remove document metadata for '{user_id}' in database."
            ) from exc

    async def get_one(self, user_id: UUID, tenant_id: UUID) -> UserEntity:
        try:
            stmt = select(User).where(
                User.user_id == user_id, User.tenant_id == tenant_id
            )
            result = await self._session.execute(stmt)
            db_user = result.scalar_one_or_none()

            if db_user is None:
                logger.warning("User with id '%s' could not be found.", user_id)
                raise UserNotFoundException(user_id)

        except SQLAlchemyError as exc:
            logger.error("Database error when fetching user %s", user_id)
            raise DatabaseInternalException(
                f"Raised database related error for '{user_id}'."
            ) from exc

        return UserMapper.to_entity(db_user)
