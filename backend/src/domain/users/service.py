import uuid
from datetime import UTC, datetime

from src.core.logger import get_logger
from src.domain.credentials.entities import CredentialsEntity
from src.domain.credentials.repository import CredentialsRepository
from src.domain.users.dataclasses import UpdateUser, User
from src.domain.users.entities import UserEntity
from src.domain.users.repository import UserRepository
from src.domain.users.schemas import CurrentUser, UserResponse
from src.shared.enums import CredentialStatus, UserRole, UserStatus
from src.utils.exceptions import (
    DatabaseException,
    NotFoundException,
    UserServiceException,
)

logger = get_logger("api.domain.user.service")


class UserService:
    """The service layer defines the business logic that ineracts with the repository."""

    def __init__(
        self,
        user_repository: UserRepository,
        credentials_repository: CredentialsRepository,
    ) -> None:
        self.user_repository = user_repository
        self.credentials_repository = credentials_repository

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
            db_user = await self.user_repository.create(entity)

            # creade initial credentials
            credentials_id = uuid.uuid4()
            credentials = CredentialsEntity(
                credentials_id=credentials_id,
                user_id=db_user.user_id,
                password_hash=user.password_hash,
                status=CredentialStatus.CREATED,
                created_at=now,
                updated_at=now,
            )
            await self.credentials_repository.create(credentials)
            return UserResponse(user_id=db_user.user_id, status=db_user.status)

        except DatabaseException:
            raise

        except Exception as exc:
            logger.warning(
                "Unexpected error occured when creating new user %s.",
                user_id,
            )
            raise UserServiceException(
                "Failed to create new user.",
            ) from exc

    async def get(self, user_id: uuid.UUID) -> CurrentUser:
        try:
            db_user = await self.user_repository.get(user_id)

            return CurrentUser(
                user_id=db_user.user_id,
                username=db_user.username,
                email=db_user.email,
                status=db_user.status,
            )
        except DatabaseException:
            raise

        except NotFoundException:
            raise

        except Exception as exc:
            logger.warning(
                "Unexpected error occured when searching for user %s.",
                user_id,
            )
            raise UserServiceException(
                "Failed to find user.",
            ) from exc

    async def update(self, user: UpdateUser, user_id: uuid.UUID) -> CurrentUser:
        try:
            db_user = await self.user_repository.get(user_id)

            # Modulate user details
            db_user.username = user.username
            db_user.email = user.email
            db_user.mark_updated()

            # Update user information
            updated = await self.user_repository.update(db_user)

            return CurrentUser(
                user_id=updated.user_id,
                email=updated.email,
                username=updated.username,
                status=db_user.status,
            )

        except DatabaseException:
            raise

        except NotFoundException:
            raise

        except Exception as exc:
            logger.warning(
                "Unexpected error occured when updating user %s.",
                user_id,
            )
            raise UserServiceException(
                "Failed to update user.",
            ) from exc

    async def deactivate(self, user_id: uuid.UUID) -> UserResponse:
        try:
            db_user = await self.user_repository.get(user_id)

            deleted_user = await self.user_repository.delete(db_user)
            return UserResponse(
                user_id=deleted_user.user_id, status=deleted_user.status
            )
        except DatabaseException:
            raise

        except NotFoundException:
            raise

        except Exception as exc:
            logger.warning(
                "Unexpected error occured when deliting user %s.",
                user_id,
            )
            raise UserServiceException(
                "Failed to delete user.",
            ) from exc