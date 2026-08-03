from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.domain.credentials.entities import CredentialsEntity
from src.domain.credentials.repository import CredentialsRepository
from src.infrastructure.database.postgres.mapper.credentials import CredentialsMapper
from src.infrastructure.database.postgres.models.credentials import (
    UserCredentials,
)
from src.shared.core.logger import get_logger
from src.shared.exception.exceptions import (
    CredentialsNotFoundException,
    DatabaseInternalException,
    DatabaseOperationException,
)

logger = get_logger("api.infra.postgres.credentials")


class PostgresCredentialsRepository(CredentialsRepository):
    def __init__(
        self,
        session: AsyncSession,
    ):
        self.session = session

    async def create(
        self,
        credentials: CredentialsEntity,
    ) -> CredentialsEntity:
        db_credentials = CredentialsMapper.to_model(credentials)

        try:
            # Add new object to session
            self.session.add(db_credentials)
            await self.session.commit()
            await self.session.refresh(db_credentials)
        except IntegrityError as exc:
            logger.warning(
                "Database error as new credentials %s for user %s exists already: %s",
                db_credentials.credentials_id,
                db_credentials.user_id,
                exc,
            )
            raise DatabaseOperationException(
                f"Credentials '{db_credentials.credentials_id}' already exists in database."
            ) from exc
        except SQLAlchemyError as exc:
            logger.warning(
                "Database error creating new credentials %s for user %s: %s",
                credentials.credentials_id,
                credentials.user_id,
                exc,
            )
            await self.session.rollback()
            raise DatabaseInternalException(
                f"Failed to store new credentials for '{credentials.credentials_id}' in database."
            ) from exc

        return CredentialsMapper.to_entity(db_credentials)  # after refresh

    async def get_one(self, credentials_id: UUID, user_id: UUID) -> CredentialsEntity:
        """Retrieve a record by its primary key."""
        try:
            stmt = select(UserCredentials).where(
                UserCredentials.credentials_id == credentials_id
            )
            result = await self.session.execute(stmt)
            db_credentials: UserCredentials | None = result.scalar_one_or_none()
        except SQLAlchemyError as exc:
            logger.warning(
                "Database error fetching credentials %s for user %s: %s",
                credentials_id,
                user_id,
                exc,
            )
            await self.session.rollback()
            raise DatabaseInternalException(
                f"Failed to read credentials for '{credentials_id}' in database."
            ) from exc

        # Enforce ownership boundaries
        if db_credentials is None or db_credentials.user_id != user_id:
            raise CredentialsNotFoundException(
                credentials_id=credentials_id
            )  # mask existence
        return CredentialsMapper.to_entity(db_credentials)

    async def update(
        self,
        credentials: CredentialsEntity,
    ) -> CredentialsEntity:

        try:
            current_db_credentials = await self.session.get(
                UserCredentials, credentials.credentials_id
            )
            if (
                current_db_credentials is None
                or current_db_credentials.user_id != credentials.user_id
            ):
                raise CredentialsNotFoundException(
                    credentials_id=credentials.credentials_id
                )  # mask existence

            # Merge objects
            db_credentials = CredentialsMapper.to_model(credentials)
            merged_credentials = await self.session.merge(db_credentials)
            await self.session.commit()
        except SQLAlchemyError as exc:
            logger.warning(
                "Database error updating credentials %s for %s: %s",
                credentials.credentials_id,
                credentials.user_id,
                exc,
            )
            await self.session.rollback()
            raise DatabaseInternalException(
                f"Failed to update credentials for '{credentials.credentials_id}' in database."
            ) from exc
        return CredentialsMapper.to_entity(merged_credentials)  # after refresh

    async def delete(
        self,
        credentials: CredentialsEntity,
    ) -> None:
        db_credentials = CredentialsMapper.to_model(credentials)

        try:
            merged_credentials = await self.session.merge(db_credentials)
            await self.session.delete(merged_credentials)
            await self.session.commit()
        except SQLAlchemyError as exc:
            logger.warning(
                "Database error removing credentials %s for %s: %s",
                credentials.credentials_id,
                credentials.user_id,
                exc,
            )
            await self.session.rollback()
            raise DatabaseInternalException(
                f"Failed to remove credentials for '{credentials.credentials_id}' in database."
            ) from exc
