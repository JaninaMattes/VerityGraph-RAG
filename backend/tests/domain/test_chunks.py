"""Tests for chunks (text units), their evidence spans and the chunking config."""

import uuid
from hashlib import sha256

import pytest

from src.domain.chunks.entities import (
    BoundingBox,
    ChunkDraft,
    ChunkingConfig,
    ChunkSpan,
    build_chunks,
)

DOCUMENT_ID = uuid.UUID("39b02a26-86d0-4dd6-ae6e-7a0ea578f290")
TENANT_ID = uuid.UUID("12bf3456-7d89-12d3-a456-78c91cf2b34f")
CONFIG = ChunkingConfig(
    component="docling-hybrid-chunker",
    component_version="2.150.1",
    model="BAAI/bge-small-en-v1.5",
    parameters={"max_tokens": 512, "merge_peers": True},
)


def span(page_no: int | None, ref: str = "#/texts/0") -> ChunkSpan:
    return ChunkSpan(source_ref=ref, label="text", page_no=page_no)


def draft(content: str = "Acme invests in Globex.", *spans: ChunkSpan) -> ChunkDraft:
    return ChunkDraft(content=content, token_count=5, spans=spans)


class TestChunkSpan:
    """A span locates part of a chunk in the source document."""

    def test_full_span_keeps_its_values(self):
        """
        GIVEN a page, a bounding box and a character range
        WHEN a span is created
        THEN it keeps every value
        """
        bbox = BoundingBox(left=72, top=728.6, right=178.7, bottom=717.5)

        result = ChunkSpan(
            source_ref="#/texts/3",
            label="text",
            page_no=2,
            bbox=bbox,
            char_start=0,
            char_end=18,
        )

        assert (result.page_no, result.bbox, result.char_end) == (2, bbox, 18)
        assert bbox.origin == "BOTTOMLEFT"

    @pytest.mark.parametrize(
        ("page_no", "char_start", "char_end"),
        [(0, None, None), (1, 5, None), (1, None, 5), (1, -1, 3), (1, 4, 3)],
        ids=["page-zero", "start-only", "end-only", "negative", "reversed"],
    )
    def test_invalid_location_is_rejected(self, page_no, char_start, char_end):
        """
        GIVEN a page below 1, half a character range, or a reversed range
        WHEN a span is created
        THEN ValueError is raised
        """
        with pytest.raises(ValueError):
            ChunkSpan(
                source_ref="#/texts/0",
                label="text",
                page_no=page_no,
                char_start=char_start,
                char_end=char_end,
            )


class TestChunkDraft:
    """A draft is the output of a chunker, before it gets an id."""

    @pytest.mark.parametrize(
        ("content", "token_count"),
        [("", 1), ("   ", 1), ("text", -1)],
        ids=["empty", "blank", "negative-tokens"],
    )
    def test_invalid_draft_is_rejected(self, content, token_count):
        """
        GIVEN blank content or a negative token count
        WHEN a draft is created
        THEN ValueError is raised
        """
        with pytest.raises(ValueError):
            ChunkDraft(content=content, token_count=token_count)


class TestChunkingConfig:
    """The config identifies how chunks were made (reproducibility, staleness)."""

    def test_hash_ignores_parameter_order(self):
        """
        GIVEN two configs that differ only in the order of their parameters
        WHEN their hashes are compared
        THEN the hashes and ids are equal
        """
        reordered = ChunkingConfig(
            component=CONFIG.component,
            component_version=CONFIG.component_version,
            model=CONFIG.model,
            parameters={"merge_peers": True, "max_tokens": 512},
        )

        assert reordered.config_hash == CONFIG.config_hash
        assert reordered.config_id == CONFIG.config_id

    @pytest.mark.parametrize(
        "change",
        [
            {"component_version": "2.151.0"},
            {"model": "other/tokenizer"},
            {"parameters": {"max_tokens": 256, "merge_peers": True}},
        ],
        ids=["version", "model", "parameters"],
    )
    def test_any_setting_changes_the_hash(self, change):
        """
        GIVEN a config with one changed setting
        WHEN its hash is compared with the original
        THEN the hash and the id differ
        """
        values = {
            "component": CONFIG.component,
            "component_version": CONFIG.component_version,
            "model": CONFIG.model,
            "parameters": CONFIG.parameters,
        } | change

        changed = ChunkingConfig(**values)

        assert changed.config_hash != CONFIG.config_hash
        assert changed.config_id != CONFIG.config_id

    def test_hash_is_sha256_hex(self):
        """
        GIVEN a config
        WHEN its hash is read
        THEN it is a 64-character lower-case hex string
        """
        assert len(CONFIG.config_hash) == 64
        int(CONFIG.config_hash, 16)


class TestBuildChunks:
    """build_chunks gives drafts deterministic ids, an order and a content hash."""

    def test_chunks_get_index_hash_and_owner(self):
        """
        GIVEN two drafts
        WHEN chunks are built
        THEN they are numbered from 0 AND carry the document, tenant and config
        AND the content hash is the SHA-256 of the content
        """
        chunks = build_chunks(
            [draft("first"), draft("second")],
            document_id=DOCUMENT_ID,
            tenant_id=TENANT_ID,
            config=CONFIG,
        )

        assert [c.chunk_index for c in chunks] == [0, 1]
        assert {(c.document_id, c.tenant_id, c.config_id) for c in chunks} == {
            (DOCUMENT_ID, TENANT_ID, CONFIG.config_id)
        }
        assert chunks[0].content_hash == sha256(b"first").hexdigest()

    def test_ids_are_deterministic(self):
        """
        GIVEN the same drafts, document and config
        WHEN chunks are built twice (for example on a retried activity)
        THEN the chunk ids are equal AND unique within the document
        """
        drafts = [draft("first"), draft("second")]

        def build():
            return build_chunks(
                drafts, document_id=DOCUMENT_ID, tenant_id=TENANT_ID, config=CONFIG
            )

        first, second = build(), build()

        assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
        assert len({c.chunk_id for c in first}) == 2

    def test_other_document_gets_other_ids(self):
        """
        GIVEN the same drafts for two documents
        WHEN chunks are built
        THEN the ids differ
        """
        other = build_chunks(
            [draft()], document_id=uuid.uuid4(), tenant_id=TENANT_ID, config=CONFIG
        )
        mine = build_chunks(
            [draft()], document_id=DOCUMENT_ID, tenant_id=TENANT_ID, config=CONFIG
        )

        assert other[0].chunk_id != mine[0].chunk_id

    @pytest.mark.parametrize(
        ("pages", "expected"),
        [
            ((1, 2, 2), (1, 2)),
            ((3,), (3, 3)),
            ((None,), (None, None)),
            ((), (None, None)),
        ],
        ids=["multi-page", "one-page", "no-page-numbers", "no-spans"],
    )
    def test_page_range_comes_from_spans(self, pages, expected):
        """
        GIVEN spans on some pages, or spans without pages
        WHEN a chunk is built
        THEN page_start and page_end are the lowest and highest page, or None
        """
        spans = tuple(span(p, f"#/texts/{i}") for i, p in enumerate(pages))

        (chunk,) = build_chunks(
            [draft("text", *spans)],
            document_id=DOCUMENT_ID,
            tenant_id=TENANT_ID,
            config=CONFIG,
        )

        assert (chunk.page_start, chunk.page_end) == expected
        assert chunk.spans == spans
