from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.domain.credentials.entities import CredentialsEntity
from src.domain.credentials.repository import CredentialsRepository
from src.infrastructure.database.postgres.mapper.credentials import CredentialsMapper
from src.infrastructure.database.postgres.models.credentials import (
    UserCredentials,
)
from src.utils.exceptions import (
    CredentialsNotFoundException,
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

        # Add new object to session
        try:
            self.session.add(db_credentials)
            await self.session.commit()
            await self.session.refresh(db_credentials)
        except SQLAlchemyError as exc:
            logger.warning(
                "Raised database related error for %s for user %s. This could be due to an invalid or conflicting function argument.",
                credentials.credentials_id,
                credentials.user_id,
            )
            await self.session.rollback()

            raise DatabaseOperationException(
                f"Failed to store new credentials for '{credentials.credentials_id}' in database."
            ) from exc

        return CredentialsMapper.to_entity(db_credentials)  # after refresh

    async def get(self, credentials_id: UUID) -> CredentialsEntity:
        """Retrieve a record by its primary key."""
        try:
            db_credentials = await self.session.get(UserCredentials, credentials_id)
        except SQLAlchemyError as exc:
            logger.warning(
                "Raised database related error for %s. This could be due to an invalid or conflicting function argument.",
                credentials_id,
            )
            await self.session.rollback()

            raise DatabaseOperationException(
                f"Failed to read credentials for '{credentials_id}' in database."
            ) from exc

        if db_credentials is None:
            raise CredentialsNotFoundException(credentials_id=credentials_id)

        return CredentialsMapper.to_entity(db_credentials)

    async def update(
        self,
        credentials: CredentialsEntity,
    ) -> CredentialsEntity:
        db_credentials = CredentialsMapper.to_model(credentials)

        # Add new object to session
        try:
            merged_credentials = await self.session.merge(db_credentials)
            await self.session.commit()
            await self.session.refresh(merged_credentials)
        except SQLAlchemyError as exc:
            logger.warning(
                "Raised database related error for %s for user %s. This could be due to an invalid or conflicting function argument.",
                credentials.credentials_id,
                credentials.user_id,
            )
            await self.session.rollback()

            raise DatabaseOperationException(
                f"Failed to update credentials for '{credentials.credentials_id}' in database."
            ) from exc

        return CredentialsMapper.to_entity(merged_credentials)  # after refresh

    async def delete(
        self,
        credentials: CredentialsEntity,
    ) -> CredentialsEntity:
        db_credentials = CredentialsMapper.to_model(credentials)

        # Add new object to session
        try:
            merged_credentials = await self.session.merge(db_credentials)
            await self.session.delete(merged_credentials)
            await self.session.commit()
        except SQLAlchemyError as exc:
            logger.warning(
                "Raised database related error for %s for user %s. This could be due to an invalid or conflicting function argument.",
                credentials.credentials_id,
                credentials.user_id,
            )
            await self.session.rollback()

            raise DatabaseOperationException(
                f"Failed to remove credentials for '{credentials.credentials_id}' in database."
            ) from exc

        return CredentialsMapper.to_entity(merged_credentials)  # after refresh
