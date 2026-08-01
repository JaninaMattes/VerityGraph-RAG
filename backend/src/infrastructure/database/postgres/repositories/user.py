from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.domain.users.entities import UserEntity
from src.domain.users.repository import UserRepository
from src.infrastructure.database.postgres.mapper.user import UserMapper
from src.infrastructure.database.postgres.models.user import User
from src.utils.exceptions import DatabaseOperationException, UserNotFoundException

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

        # Add new object to session
        try:
            self.session.add(db_user)
            await self.session.commit()
            await self.session.refresh(db_user)
        except SQLAlchemyError as exc:
            logger.warning(
                "Raised database related error for %s. This could be due to an invalid or conflicting function argument.",
                user.user_id,
            )
            await self.session.rollback()

            raise DatabaseOperationException(
                f"Failed to create new user entry for '{db_user.user_id}' in database."
            ) from exc

        return UserMapper.to_entity(db_user)  # after rerfesh

    async def get(self, user_id: UUID) -> UserEntity:
        try:
            db_user = await self.session.get(User, user_id)
        except SQLAlchemyError as exc:
            logger.warning(
                "Raised database related error for %s. This could be due to an invalid or conflicting function argument.",
                user_id,
            )
            await self.session.rollback()

            raise DatabaseOperationException(
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
            logger.exception(
                "Failed to update user metadata with ID %s",
                db_user.user_id,
            )
            await self.session.rollback()

            raise DatabaseOperationException(
                f"Failed to update user metadata with ID '{db_user.user_id}'."
            ) from exc

        return UserMapper.to_entity(merged_user)  # after refresh


    async def delete(
        self,
        user: UserEntity,
    ) -> UserEntity:

        db_user = UserMapper.to_model(user)

        try:
            merged_user = await self.session.merge(db_user)
            await self.session.delete(merged_user)
            await self.session.commit()
        except SQLAlchemyError as exc:
            logger.exception(
                "Failed to remove user metadata with ID %s",
                db_user.user_id,
            )
            await self.session.rollback()

            raise DatabaseOperationException(
                f"Failed to remove user metadata with ID '{db_user.user_id}'."
            ) from exc

        return UserMapper.to_entity(merged_user)
