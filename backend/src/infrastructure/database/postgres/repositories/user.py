from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.domain.users.entities import UserEntity
from src.domain.users.repository import UserRepository
from src.infrastructure.database.postgres.mapper.user import UserMapper
from src.infrastructure.database.postgres.models.user import User
from src.shared.core.logger import get_logger
from src.shared.exception.exceptions import (
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
        self.session = session

    async def create(
        self,
        user: UserEntity,
    ) -> UserEntity:
        db_user = UserMapper.to_model(user)
        try:
            # Add new object to session
            self.session.add(db_user)
            await self.session.commit()
            await self.session.refresh(db_user)
        except IntegrityError as exc:
            logger.warning(
                "Database error as new user %s exists already: %s",
                user.user_id,
                exc,
            )
            raise DatabaseOperationException(
                f"User '{db_user.user_id}' already exists in database."
            ) from exc
        except SQLAlchemyError as exc:
            logger.warning("Database error creating new user %s: %s", user.user_id, exc)
            await self.session.rollback()
            raise DatabaseInternalException(
                f"Failed to create new user entry for '{db_user.user_id}' in database."
            ) from exc

        return UserMapper.to_entity(db_user)  # after rerfesh

    async def get_one(self, user_id: UUID) -> UserEntity:
        try:
            stmt = select(User).where(User.user_id == user_id)
            result = await self.session.execute(stmt)
            db_user: User | None = result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            logger.warning("Database error fetching user %s: %s", user_id, exc)
            await self.session.rollback()
            raise DatabaseInternalException(
                f"Raised database related error for '{user_id}'."
            ) from exc

        if db_user is None:
            logger.warning(
                "Raised database related error for %s. The user could not be found.",
                user_id,
            )
            raise UserNotFoundException(user_id=user_id)

        return UserMapper.to_entity(db_user)

    async def update(
        self,
        user: UserEntity,
    ) -> UserEntity:
        db_user = UserMapper.to_model(user)

        # Merge objects
        try:
            merged_user = await self.session.merge(db_user)
            await self.session.commit()
            await self.session.refresh(merged_user)
        except SQLAlchemyError as exc:
            logger.warning("Database error updating user %s: %s", user.user_id, exc)
            await self.session.rollback()
            raise DatabaseInternalException(
                f"Failed to update user metadata with ID '{db_user.user_id}'."
            ) from exc

        return UserMapper.to_entity(merged_user)  # after refresh

    async def delete(
        self,
        user: UserEntity,
    ) -> None:

        db_user = UserMapper.to_model(user)

        try:
            merged_user = await self.session.merge(db_user)
            await self.session.delete(merged_user)
            await self.session.commit()
        except SQLAlchemyError as exc:
            logger.warning("Database error removing user %s: %s", user.user_id, exc)
            await self.session.rollback()
            raise DatabaseInternalException(
                f"Failed to remove user metadata with ID '{db_user.user_id}'."
            ) from exc
