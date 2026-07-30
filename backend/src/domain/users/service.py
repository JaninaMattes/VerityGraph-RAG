import uuid
from datetime import UTC, datetime

from src.core.logger import get_logger
from src.domain.users.dataclasses import User
from src.domain.users.entities import UserEntity
from src.domain.users.repository import UserRepository
from src.domain.users.schemas import CurrentUser, UserResponse
from src.shared.enums import UserRole, UserStatus
from src.utils.exceptions import UserNotFoundException, UserServiceError

logger = get_logger("api-backend.domain.user.service")


class UserService:
    """The service layer defines the business logic that ineracts with the repository."""

    def __init__(
        self,
        repository: UserRepository,
    ) -> None:
        self.repository = repository

    async def create(self, user: User, tenant_id: uuid.UUID) -> UserResponse:
        # Randomly generate new UUID
        user_id = uuid.uuid4()

        # Persist metadata
        now = datetime.now(UTC)
        now = datetime.now(UTC)
        entity = UserEntity(
            user_id=user_id,
            tenant_id=tenant_id,
            username=user.username,
            email=user.email,
            roles=[UserRole.USER],
            created_at=now,
            updated_at=now,
            status=UserStatus.CREATED,
        )

        try:
            db_user = await self.repository.create(entity)
            return UserResponse(user_id=db_user.user_id, status=db_user.status)
        except Exception as e:
            logger.exception(
                f"Failed to create new user with ID '{user_id}' in database!",
            )
            raise UserServiceError(
                "Tenant Service Error",
                f"Failed to create new user with ID '{user_id}' in database!",
            ) from e

    async def get(self, user_id: uuid.UUID) -> CurrentUser:
        try:
            db_user = await self.repository.get(user_id)

            if db_user is None:
                raise UserNotFoundException(
                    name="User Service Error",
                    message=f"Requested user with ID {user_id} not found!",
                )
            return CurrentUser(
                user_id=db_user.user_id,
                username=db_user.username,
                status=db_user.status,
            )
        except Exception as e:
            logger.exception(
                f"Failed to get user with ID '{user_id}' from database!",
            )
            raise UserServiceError(
                "Tenant Service Error",
                f"Failed to get user with ID '{user_id}' from database!",
            ) from e

    async def update(self, user: User, user_id: uuid.UUID) -> CurrentUser:
        try:
            db_user = await self.repository.get(user_id)

            if db_user is None:
                raise UserNotFoundException(
                    name="User Service Error",
                    message=f"Requested user with ID {user_id} not found!",
                )

            # Modulate user details
            db_user.username = user.username
            db_user.email = user.email
            db_user.mark_updated()

            # Update user information
            updated = await self.repository.update(db_user)

            return CurrentUser(
                user_id=updated.user_id,
                username=updated.username,
                status=db_user.status,
            )

        except Exception as e:
            logger.exception(
                f"Failed to update user with ID '{user_id}' in database!",
            )
            raise UserServiceError(
                "Tenant Service Error",
                f"Failed to update user with ID '{user_id}' in database!",
            ) from e

    async def deactivate(self, user_id: uuid.UUID) -> UserResponse:
        try:
            db_user = await self.repository.get(user_id)

            if db_user is None:
                raise UserNotFoundException(
                    name="User Service Error",
                    message=f"Requested user with ID {user_id} not found!",
                )

            deleted_user = await self.repository.delete(db_user)
            return UserResponse(
                user_id=deleted_user.user_id, status=deleted_user.status
            )

        except Exception as e:
            logger.exception(
                f"Failed to delete user with ID '{user_id}' from database!",
            )
            raise UserServiceError(
                "Tenant Service Error",
                f"Failed to delete user with ID '{user_id}' from database!",
            ) from e
