from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from src.utils.exceptions import UserNotFoundException
from src.infrastructure.database.postgres.mapper.user import UserMapper
from src.infrastructure.database.postgres.models.user import User
from src.domain.users.entities import UserEntity
from src.application.port.user_repository import UserRepository
from src.core.logger import get_logger

logger = get_logger("api-backend.infra.postgres.user")


class PostgresTenantRepository(UserRepository):
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
        except Exception as e:
            logger.error(
                f"Failed to create new user with ID {user.user_id}! Error: {e}",
                exc_info=True,
            )
            await self.session.rollback()
            raise

        return UserMapper.to_entity(db_user)  # after rerfesh

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
        except Exception as e:
            logger.error(
                f"Failed to update user with ID {user.user_id}! Error: {e}",
                exc_info=True,
            )
            await self.session.rollback()
            raise

        return UserMapper.to_entity(merged_user)  # after refresh

    async def get(self, user_id: UUID) -> UserEntity:
        try:
            db_user = await self.session.get(User, user_id)
        except Exception as e:
            logger.error(
                f"Failed to retrieve user with ID {user_id}! Error: {e}",
                exc_info=True,
            )
            await self.session.rollback()
            raise

        if db_user is None:
            raise UserNotFoundException(
                name="Tenant Repository Error",
                message=f"Requested tenant with ID {user_id} not found!",
            )

        return UserMapper.to_entity(db_user)

    async def delete(
        self,
        user: UserEntity,
    ) -> UserEntity:

        db_user = UserMapper.to_model(user)

        try:
            merged_user = await self.session.merge(db_user)
            await self.session.delete(merged_user)
            await self.session.commit()
        except Exception as e:
            logger.error(
                f"Failed to delete tenant with ID {user.user_id}! Error: {e}",
                exc_info=True,
            )
            await self.session.rollback()
            raise

        return UserMapper.to_entity(merged_user)
