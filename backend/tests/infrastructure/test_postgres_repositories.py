"""Tests for the PostgreSQL repositories with a mocked AsyncSession.

Rules under test:
- repositories flush but never commit (the caller owns the transaction);
- a missing row raises the entity-specific NotFoundException;
- SQLAlchemy errors are translated to DatabaseException subclasses.
"""

import uuid
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError, OperationalError
from src.infrastructure.database.postgres.mapper.document import DocumentMapper
from src.infrastructure.database.postgres.mapper.ingestionjob import IngestionJobMapper
from src.infrastructure.database.postgres.mapper.tenant import TenantMapper
from src.infrastructure.database.postgres.mapper.user import UserMapper
from src.infrastructure.database.postgres.repositories.document import (
    PostgresDocumentRepository,
)
from src.infrastructure.database.postgres.repositories.ingestionjobs import (
    PostgresIngestionJobRepository,
)
from src.infrastructure.database.postgres.repositories.tenant import (
    PostgresTenantRepository,
)
from src.infrastructure.database.postgres.repositories.user import (
    PostgresUserRepository,
)
from src.libs.enums.credentials import CredentialStatus
from src.libs.exceptions.exceptions import (
    ConflictException,
    DatabaseException,
    DocumentNotFoundException,
    IngestionJobNotFoundException,
    TenantNotFoundException,
    UserNotFoundException,
)

DB_ERROR = OperationalError("SELECT 1", {}, Exception("connection lost"))
CONFLICT = IntegrityError("INSERT", {}, Exception("duplicate key"))


@dataclass
class Case:
    """One repository with its entity fixture, key arguments and not-found error."""

    repo_cls: type
    mapper: Any
    entity_fixture: str
    key_attrs: tuple[str, ...]
    not_found: type[Exception]
    idempotent_create: bool

    def keys(self, entity: Any) -> tuple[Any, ...]:
        return tuple(getattr(entity, attr) for attr in self.key_attrs)


CASES = [
    Case(
        PostgresDocumentRepository,
        DocumentMapper,
        "document_entity",
        ("document_id", "tenant_id"),
        DocumentNotFoundException,
        idempotent_create=True,
    ),
    Case(
        PostgresIngestionJobRepository,
        IngestionJobMapper,
        "job_entity",
        ("job_id", "document_id"),
        IngestionJobNotFoundException,
        idempotent_create=True,
    ),
    Case(
        PostgresTenantRepository,
        TenantMapper,
        "tenant_entity",
        ("tenant_id",),
        TenantNotFoundException,
        idempotent_create=False,
    ),
    Case(
        PostgresUserRepository,
        UserMapper,
        "user_entity",
        ("user_id", "tenant_id"),
        UserNotFoundException,
        idempotent_create=False,
    ),
]
IDS = ["document", "job", "tenant", "user"]


@pytest.fixture(params=CASES, ids=IDS)
def case(request: pytest.FixtureRequest) -> Case:
    return request.param


@pytest.fixture
def entity(case: Case, request: pytest.FixtureRequest) -> Any:
    return request.getfixturevalue(case.entity_fixture)


def result_with(row: Any = None, rowcount: int = 1) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    result.rowcount = rowcount
    return result


class TestGetOne:
    """get_one returns the entity or raises the entity-specific NotFoundException."""

    async def test_found_row_is_mapped_to_entity(self, case, entity, mock_db_session):
        """
        GIVEN the row exists
        WHEN get_one is called with its keys
        THEN the mapped entity is returned
        """
        mock_db_session.execute.return_value = result_with(case.mapper.to_model(entity))

        found = await case.repo_cls(mock_db_session).get_one(*case.keys(entity))

        assert found == entity

    async def test_missing_row_raises_not_found(self, case, entity, mock_db_session):
        """
        GIVEN no row matches
        WHEN get_one is called
        THEN the entity-specific NotFoundException is raised
        """
        mock_db_session.execute.return_value = result_with(None)

        with pytest.raises(case.not_found):
            await case.repo_cls(mock_db_session).get_one(*case.keys(entity))

    async def test_database_error_is_translated(self, case, entity, mock_db_session):
        """
        GIVEN the database fails
        WHEN get_one is called
        THEN DatabaseException is raised
        """
        mock_db_session.execute.side_effect = DB_ERROR

        with pytest.raises(DatabaseException):
            await case.repo_cls(mock_db_session).get_one(*case.keys(entity))


class TestDelete:
    """delete removes exactly one row, without committing."""

    async def test_existing_row_is_deleted(self, case, entity, mock_db_session):
        """
        GIVEN the row exists
        WHEN delete is called
        THEN one DELETE runs AND the session is not committed
        """
        mock_db_session.execute.return_value = result_with(rowcount=1)

        await case.repo_cls(mock_db_session).delete(*case.keys(entity))

        mock_db_session.execute.assert_awaited_once()
        mock_db_session.commit.assert_not_awaited()

    async def test_missing_row_raises_not_found(self, case, entity, mock_db_session):
        """
        GIVEN no row matches
        WHEN delete is called
        THEN the entity-specific NotFoundException is raised
        """
        mock_db_session.execute.return_value = result_with(rowcount=0)

        with pytest.raises(case.not_found):
            await case.repo_cls(mock_db_session).delete(*case.keys(entity))

    async def test_database_error_is_translated(self, case, entity, mock_db_session):
        """
        GIVEN the database fails
        WHEN delete is called
        THEN DatabaseException is raised
        """
        mock_db_session.execute.side_effect = DB_ERROR

        with pytest.raises(DatabaseException):
            await case.repo_cls(mock_db_session).delete(*case.keys(entity))


class TestWrite:
    """create and update flush the change and return the stored entity."""

    async def test_create_flushes_without_commit(self, case, entity, mock_db_session):
        """
        GIVEN a new entity
        WHEN create is called
        THEN the row is written (merge for idempotent repositories, add otherwise)
        AND the session is flushed but not committed
        """
        mock_db_session.merge.side_effect = lambda model: model

        created = await case.repo_cls(mock_db_session).create(entity)

        assert created == entity
        if case.idempotent_create:
            mock_db_session.merge.assert_awaited_once()
        else:
            mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_awaited_once()
        mock_db_session.commit.assert_not_awaited()

    async def test_update_merges_without_commit(self, case, entity, mock_db_session):
        """
        GIVEN an existing entity
        WHEN update is called
        THEN the row is merged and flushed AND the session is not committed
        """
        mock_db_session.merge.side_effect = lambda model: model

        updated = await case.repo_cls(mock_db_session).update(entity)

        assert updated == entity
        mock_db_session.merge.assert_awaited_once()
        mock_db_session.flush.assert_awaited_once()
        mock_db_session.commit.assert_not_awaited()

    @pytest.mark.parametrize("method", ["create", "update"])
    async def test_conflict_raises_operation_exception(
        self, case, entity, mock_db_session, method
    ):
        """
        GIVEN the database rejects the write with an integrity error (duplicate)
        WHEN create or update is called
        THEN ConflictException is raised
        """
        mock_db_session.flush.side_effect = CONFLICT

        with pytest.raises(ConflictException):
            await getattr(case.repo_cls(mock_db_session), method)(entity)

    @pytest.mark.parametrize("method", ["create", "update"])
    async def test_database_error_is_translated(
        self, case, entity, mock_db_session, method
    ):
        """
        GIVEN the database fails during the write
        WHEN create or update is called
        THEN DatabaseException is raised
        """
        mock_db_session.flush.side_effect = DB_ERROR

        with pytest.raises(DatabaseException):
            await getattr(case.repo_cls(mock_db_session), method)(entity)


class TestUnknownKeys:
    """Unknown ids are reported with the id that was requested."""

    async def test_not_found_message_names_the_id(self, mock_db_session):
        """
        GIVEN no tenant with the requested id
        WHEN get_one is called
        THEN the error message names the requested id
        """
        tenant_id = uuid.uuid4()
        mock_db_session.execute.return_value = result_with(None)

        with pytest.raises(TenantNotFoundException, match=str(tenant_id)):
            await PostgresTenantRepository(mock_db_session).get_one(tenant_id)


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Override: a plain session mock with a synchronous add()."""
    session = AsyncMock()
    session.add = MagicMock()
    return session


class TestUserCredentials:
    """The user repository stores and finds the local password of a user."""

    async def test_create_with_password_hash_adds_local_credential(
        self, user_entity, mock_db_session
    ):
        """
        GIVEN a new user and the hash of its password
        WHEN the user is created
        THEN the stored user has one valid 'local' credential with that hash
        """
        await PostgresUserRepository(mock_db_session).create(user_entity, "hash")

        (model,) = mock_db_session.add.call_args.args
        (credential,) = model.credentials
        assert (credential.provider, credential.password_hash) == ("local", "hash")
        assert credential.status is CredentialStatus.VALID

    async def test_create_without_password_hash_adds_no_credential(
        self, user_entity, mock_db_session
    ):
        """
        GIVEN a new user without a password (for example a future SSO user)
        WHEN the user is created
        THEN no credential is stored
        """
        await PostgresUserRepository(mock_db_session).create(user_entity)

        (model,) = mock_db_session.add.call_args.args
        assert model.credentials == []

    async def test_find_login_candidates_maps_rows(self, user_entity, mock_db_session):
        """
        GIVEN the query returns one user row with its hash
        WHEN the login candidates are read
        THEN the result is the user entity with that hash
        """
        result = MagicMock()
        result.all.return_value = [(UserMapper.to_model(user_entity), "hash")]
        mock_db_session.execute.return_value = result

        candidates = await PostgresUserRepository(
            mock_db_session
        ).find_login_candidates(user_entity.email)

        assert candidates == [(user_entity, "hash")]
