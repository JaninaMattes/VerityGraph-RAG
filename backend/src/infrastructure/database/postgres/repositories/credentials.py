from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.domain.credentials.entities import CredentialsEntity
from src.domain.credentials.repository import CredentialsRepository
from src.infrastructure.database.postgres.mapper.credentials import CredentialsMapper
from src.infrastructure.database.postgres.models.credentials import (
    UserCredentials,
)
from src.utils.exceptions import CredentialsNotFoundException, PostgreSQLOperationError

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
        except Exception as e:
            logger.exception(
                f"Failed to create new entry for user credentials with ID {credentials.credentials_id!r}!",
            )
            await self.session.rollback()
            raise PostgreSQLOperationError(
                "PostgreSQL DB Error",
                f"Failed to create new entry for user credentials with ID {credentials.credentials_id!r}!",
            ) from e

        return CredentialsMapper.to_entity(db_credentials)  # after refresh

    async def get(self, credentials_id: UUID) -> CredentialsEntity:
        """Retrieve a record by its primary key."""
        try:
            db_credentials = await self.session.get(UserCredentials, credentials_id)
            if db_credentials is None:
                raise CredentialsNotFoundException(
                    name="Credentials Repository Error",
                    message=f"Requested document with ID {credentials_id} not found!",
                )
        except Exception as e:
            logger.exception(
                f"Failed to get user credentials with ID {credentials_id!r}!",
            )
            await self.session.rollback()
            raise PostgreSQLOperationError(
                "PostgreSQL DB Error",
                f"Failed to get user credentials with ID {credentials_id!r}!",
            ) from e

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
        except Exception as e:
            logger.exception(
                f"Failed to update user credentials with ID {credentials.credentials_id!r}!",
            )
            await self.session.rollback()
            raise PostgreSQLOperationError(
                "PostgreSQL DB Error",
                f"Failed to update user credentials with ID {credentials.credentials_id!r}!",
            ) from e

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
        except Exception as e:
            logger.exception(
                f"Failed to update user credentials with ID {credentials.credentials_id!r}!",
            )
            await self.session.rollback()
            raise PostgreSQLOperationError(
                "PostgreSQL DB Error",
                f"Failed to update user credentials with ID {credentials.credentials_id!r}!",
            ) from e

        return CredentialsMapper.to_entity(merged_credentials)  # after refresh
