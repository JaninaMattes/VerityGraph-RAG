"""Shared SQL helpers for the PostgreSQL repositories.

Rules for every repository:
- write and flush, but never commit: the caller owns the transaction;
- a missing row raises the entity-specific NotFoundException;
- IntegrityError becomes DatabaseOperationException, other SQLAlchemy errors
  become DatabaseInternalException.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Delete, Select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.postgres.base import Base
from src.libs.core.logger import get_logger
from src.libs.exceptions.exceptions import (
    DatabaseInternalException,
    DatabaseOperationException,
    NotFoundException,
)

logger = get_logger("api.infra.postgres")


@contextmanager
def translate_db_errors(action: str) -> Iterator[None]:
    """Translate SQLAlchemy errors raised while doing `action` to DatabaseException."""
    try:
        yield
    except IntegrityError as exc:
        logger.warning("Conflict while trying to %s: %s", action, exc.orig)
        raise DatabaseOperationException(f"Conflict while trying to {action}.") from exc
    except SQLAlchemyError as exc:
        logger.error("Database error while trying to %s: %s", action, exc)
        raise DatabaseInternalException(f"Failed to {action}.") from exc


class PostgresRepository:
    """Base class that holds the session and the shared query helpers."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _scalar_one(
        self, statement: Select[Any], not_found: NotFoundException
    ) -> Any:
        """Return the single row of `statement`, or raise `not_found` if there is none."""
        with translate_db_errors("read a row"):
            row = (await self._session.execute(statement)).scalar_one_or_none()
        if row is None:
            raise not_found
        return row

    async def _delete_one(
        self, statement: Delete, not_found: NotFoundException
    ) -> None:
        """Run the DELETE `statement`, or raise `not_found` if it matched no row."""
        with translate_db_errors("delete a row"):
            result = await self._session.execute(statement)
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise not_found

    async def _add(self, model: Base) -> Base:
        """Insert a new row. A duplicate key raises DatabaseOperationException."""
        with translate_db_errors("insert a row"):
            self._session.add(model)
            await self._session.flush()
        return model

    async def _merge(self, model: Base) -> Base:
        """Insert the row, or overwrite the row with the same primary key."""
        with translate_db_errors("save a row"):
            merged = await self._session.merge(model)
            await self._session.flush()
        return merged
