"""Tests for the PostgreSQL engine, session factory, request session and mappers."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.documents.dataclasses import DocumentChecksum
from src.infrastructure.database.postgres.engine import create_async_db_engine
from src.infrastructure.database.postgres.mapper.document import DocumentMapper
from src.infrastructure.database.postgres.mapper.ingestionjob import IngestionJobMapper
from src.infrastructure.database.postgres.mapper.tenant import TenantMapper
from src.infrastructure.database.postgres.mapper.user import UserMapper
from src.infrastructure.database.postgres.models import (
    Document,
    DocumentChunk,
    IngestionJob,
    Tenant,
    User,
    UserCredentials,
)
from src.infrastructure.database.postgres.session import (
    create_session_factory,
    get_db_session,
)
from src.libs.core.config import Settings


class TestEngine:
    """The engine uses the configured URL and a bounded connection pool."""

    async def test_engine_uses_settings(self, test_settings: Settings):
        """
        GIVEN settings with a pool size
        WHEN the engine is created
        THEN it targets the configured database with that pool size
        """
        engine = create_async_db_engine(test_settings)

        assert engine.url.database == "test"
        assert engine.pool.size() == test_settings.postgres_pool_size
        await engine.dispose()

    async def test_session_factory_does_not_expire_on_commit(
        self, test_settings: Settings
    ):
        """
        GIVEN an engine
        WHEN a session factory is created
        THEN sessions keep loaded attributes after commit (required for async use)
        """
        engine = create_async_db_engine(test_settings)

        factory = create_session_factory(engine)

        assert factory.kw["expire_on_commit"] is False
        await engine.dispose()


def request_with(session: AsyncMock) -> SimpleNamespace:
    factory = MagicMock(return_value=session)
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(session_factory=factory))
    )


@pytest.mark.asyncio
class TestRequestSession:
    """get_db_session is the unit of work of one HTTP request."""

    async def test_success_commits(self, mock_db_session: AsyncMock):
        """
        GIVEN a request that finishes without an error
        WHEN the session dependency closes
        THEN the session commits once AND never rolls back
        """
        sessions = get_db_session(request_with(mock_db_session))  # type: ignore[arg-type]

        assert await anext(sessions) is mock_db_session
        with pytest.raises(StopAsyncIteration):
            await anext(sessions)

        mock_db_session.commit.assert_awaited_once()
        mock_db_session.rollback.assert_not_awaited()

    async def test_error_rolls_back_and_reraises(self, mock_db_session: AsyncMock):
        """
        GIVEN a request that fails with an error
        WHEN the session dependency closes
        THEN the session rolls back AND the error propagates AND nothing is committed
        """
        sessions = get_db_session(request_with(mock_db_session))  # type: ignore[arg-type]
        await anext(sessions)

        with pytest.raises(ValueError, match="boom"):
            await sessions.athrow(ValueError("boom"))

        mock_db_session.rollback.assert_awaited_once()
        mock_db_session.commit.assert_not_awaited()


class TestMappers:
    """Each mapper converts entity -> model -> entity without losing data."""

    @pytest.mark.parametrize(
        ("mapper", "fixture"),
        [
            (DocumentMapper, "document_entity"),
            (IngestionJobMapper, "job_entity"),
            (TenantMapper, "tenant_entity"),
            (UserMapper, "user_entity"),
        ],
        ids=["document", "job", "tenant", "user"],
    )
    def test_round_trip_keeps_all_fields(self, mapper, fixture, request):
        """
        GIVEN a domain entity
        WHEN it is mapped to an ORM model and back
        THEN every attribute equals the original
        """
        entity = request.getfixturevalue(fixture)

        restored = mapper.to_entity(mapper.to_model(entity))

        assert vars(restored) == vars(entity)

    @pytest.mark.parametrize(
        ("model", "name"),
        [
            (Document(document_id=uuid.uuid4(), filename="a.pdf"), "Document("),
            (DocumentChunk(chunk_id=uuid.uuid4(), chunk_index=1), "Chunk("),
            (IngestionJob(job_id=uuid.uuid4()), "IngestionJob("),
            (Tenant(tenant_id=uuid.uuid4(), organisation="ACME"), "Tenant("),
            (User(user_id=uuid.uuid4(), username="ada"), "User("),
            (UserCredentials(credentials_id=uuid.uuid4()), "UserCredentials("),
        ],
        ids=["document", "chunk", "job", "tenant", "user", "credentials"],
    )
    def test_model_repr_is_readable(self, model, name):
        """
        GIVEN an ORM model
        WHEN it is printed
        THEN the text names the model and is a closed expression
        """
        text = repr(model)

        assert text.startswith(name)
        assert text.endswith(")")

    def test_document_checksum_round_trip(self, document_entity):
        """
        GIVEN a document with a checksum
        WHEN it is mapped to a model and back
        THEN the model stores the hex string AND the entity gets the value object back
        """
        document_entity.checksum = DocumentChecksum.from_bytes(b"x")

        model = DocumentMapper.to_model(document_entity)
        restored = DocumentMapper.to_entity(model)

        assert model.checksum == document_entity.checksum.value
        assert restored.checksum == document_entity.checksum
