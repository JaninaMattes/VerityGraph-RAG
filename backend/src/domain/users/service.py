from datetime import datetime, timezone
import uuid

from src.shared.enums import UserStatus
from src.domain.users.dataclasses import User
from src.domain.users.entities import UserEntity
from src.domain.users.schemas import CurrentUser, Response
from src.application.port.user_repository import UserRepository
from src.utils.exceptions import UserNotFoundException
from src.core.logger import get_logger

logger = get_logger("api-backend.domain.user.service")


class UserService:
    """The service layer defines the business logic that ineracts with the repository."""

    def __init__(
        self,
        repository: UserRepository,
    ) -> None:
        self.repository = repository

    async def create(
        self, user: User, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Response:
        user_id = uuid.uuid4()

        # Persist metadata
        now = datetime.now(timezone.utc)
        entity = UserEntity(
            user_id=user_id,
            tenant_id=tenant_id,
            username=user.username,
            email=user.email,
            created_at=now,
            updated_at=now,
            status=UserStatus.CREATED,
        )

        try:
            db_user = await self.repository.create(entity)
            return Response(user_id=db_user.user_id, status=db_user.status)
        except Exception as e:
            logger.error(
                f"Failed to create new user {user_id} object. Error: {e}",
                exc_info=True,
            )
            raise

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
            logger.error(
                f"Failed to retrieve user {user_id}. Error: {e}",
                exc_info=True,
            )
            raise

    async def update(self, user: User, user_id: uuid.UUID) -> Response:
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

            return Response(user_id=updated.user_id, status=db_user.status)

        except Exception as e:
            logger.error(
                f"Failed to update tenant {user_id}. Error: {e}",
                exc_info=True,
            )
            raise

    async def delete(self, user_id: uuid.UUID) -> Response:
        try:
            db_user = await self.repository.get(user_id)

            if db_user is None:
                raise UserNotFoundException(
                    name="User Service Error",
                    message=f"Requested user with ID {user_id} not found!",
                )

            deleted_user = await self.repository.delete(db_user)
            return Response(user_id=deleted_user.user_id, status=deleted_user.status)

        except Exception as e:
            logger.error(
                f"Failed to delete user {user_id}. Error: {e}",
                exc_info=True,
            )
            raise
