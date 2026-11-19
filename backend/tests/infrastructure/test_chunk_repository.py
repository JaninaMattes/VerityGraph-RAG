"""Tests for the chunk mapper and the PostgreSQL chunk repository (mocked session).

The SQL itself runs against a real database in tests/integration.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import OperationalError
from src.domain.chunks.entities import (
    BoundingBox,
    ChunkDraft,
    ChunkingConfig,
    ChunkSpan,
    build_chunks,
)
from src.infrastructure.database.postgres.mapper.chunk import ChunkMapper
from src.infrastructure.database.postgres.models import PipelineConfig
from src.infrastructure.database.postgres.repositories.chunk import (
    PostgresChunkRepository,
)
from src.libs.enums.pipeline import PipelineKind
from src.libs.exceptions.exceptions import DatabaseException

DOCUMENT_ID = uuid.uuid4()
TENANT_ID = uuid.uuid4()
CONFIG = ChunkingConfig(
    component="docling-hybrid-chunker",
    component_version="2.150.1",
    model="BAAI/bge-small-en-v1.5",
    parameters={"max_tokens": 512},
)
SPANS = (
    ChunkSpan(
        source_ref="#/texts/0",
        label="section_header",
        page_no=1,
        bbox=BoundingBox(72, 728.5, 180, 717.5),
        char_start=0,
        char_end=11,
    ),
    ChunkSpan(source_ref="#/tables/0", label="table", page_no=2),
)
CHUNKS = build_chunks(
    [
        ChunkDraft(
            content="Investments\nAcme invests in Globex.",
            token_count=7,
            headings=("Investments",),
            spans=SPANS,
        ),
        ChunkDraft(content="Risk factors.", token_count=2),
    ],
    document_id=DOCUMENT_ID,
    tenant_id=TENANT_ID,
    config=CONFIG,
)


@pytest.fixture
def session() -> AsyncMock:
    session = AsyncMock()
    session.add_all = MagicMock()
    return session


class TestChunkMapper:
    """The mapper converts chunks with spans to rows and back without loss."""

    def test_round_trip_keeps_chunk_and_spans(self):
        """
        GIVEN a chunk with a heading and two spans (one with a box, one without)
        WHEN it is mapped to a model and back
        THEN the restored chunk equals the original
        """
        model = ChunkMapper.to_model(CHUNKS[0])

        assert ChunkMapper.to_entity(model) == CHUNKS[0]

    def test_model_stores_page_range_and_span_order(self):
        """
        GIVEN a chunk whose spans are on pages 1 and 2
        WHEN it is mapped to a model
        THEN the row has page_start 1 and page_end 2 AND the spans are numbered
        """
        model = ChunkMapper.to_model(CHUNKS[0])

        assert (model.page_start, model.page_end) == (1, 2)
        assert [s.span_index for s in model.spans] == [0, 1]
        assert model.spans[0].bbox_left == 72

    def test_config_row_has_deterministic_id(self):
        """
        GIVEN a chunking config
        WHEN it is mapped to a row
        THEN the row id is the config id AND the kind is CHUNKING
        """
        row = ChunkMapper.config_to_model(CONFIG)

        assert isinstance(row, PipelineConfig)
        assert row.config_id == CONFIG.config_id
        assert row.kind is PipelineKind.CHUNKING
        assert row.config_hash == CONFIG.config_hash


class TestReplaceForDocument:
    """replace_for_document swaps all chunks of a document in one transaction."""

    async def test_config_is_upserted_old_chunks_deleted_new_added(self, session):
        """
        GIVEN new chunks for a document
        WHEN they replace the old chunks
        THEN the config is upserted, the old spans and chunks are deleted, the new
            rows are added and flushed, AND the session is not committed
        """
        await PostgresChunkRepository(session).replace_for_document(
            DOCUMENT_ID, TENANT_ID, CONFIG, CHUNKS
        )

        upsert, delete_spans, delete_chunks = (
            call.args[0] for call in session.execute.await_args_list
        )
        assert "ON CONFLICT" in str(upsert).upper()
        assert str(delete_spans).startswith("DELETE FROM chunk_span")
        assert str(delete_chunks).startswith("DELETE FROM document_chunk")
        (rows,) = session.add_all.call_args.args
        assert [row.chunk_id for row in rows] == [c.chunk_id for c in CHUNKS]
        session.flush.assert_awaited_once()
        session.commit.assert_not_awaited()

    async def test_database_error_is_translated(self, session):
        """
        GIVEN the database fails
        WHEN chunks are replaced
        THEN DatabaseException is raised
        """
        session.execute.side_effect = OperationalError("DELETE", {}, Exception("down"))

        with pytest.raises(DatabaseException):
            await PostgresChunkRepository(session).replace_for_document(
                DOCUMENT_ID, TENANT_ID, CONFIG, CHUNKS
            )


class TestListForDocument:
    """list_for_document returns the chunks of one tenant's document in order."""

    async def test_rows_are_mapped_to_chunks(self, session):
        """
        GIVEN two stored chunks
        WHEN the chunks of the document are listed
        THEN they are returned as domain chunks
        """
        rows = [ChunkMapper.to_model(chunk) for chunk in CHUNKS]
        result = MagicMock()
        result.scalars.return_value.all.return_value = rows
        session.execute.return_value = result

        chunks = await PostgresChunkRepository(session).list_for_document(
            DOCUMENT_ID, TENANT_ID
        )

        assert chunks == CHUNKS
        query = str(session.execute.await_args.args[0])
        assert "ORDER BY document_chunk.chunk_index" in query

    async def test_database_error_is_translated(self, session):
        """
        GIVEN the database fails
        WHEN the chunks are listed
        THEN DatabaseException is raised
        """
        session.execute.side_effect = OperationalError("SELECT", {}, Exception("down"))

        with pytest.raises(DatabaseException):
            await PostgresChunkRepository(session).list_for_document(
                DOCUMENT_ID, TENANT_ID
            )
