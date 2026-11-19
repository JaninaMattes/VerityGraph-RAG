"""Chunks (GraphRAG "text units") and the evidence that links them to the source.

A chunk is the unit that embeddings, entity extraction and citations refer to. Each
span says where one part of the chunk comes from in the source document (page,
box, character range), so a client can highlight the evidence.

Chunk ids are deterministic: the same document, chunking config and position give
the same id. A retried or repeated run therefore produces the same ids, and the
derived stores (Qdrant, Neo4j) can upsert by id.
"""

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid5

# Fixed namespaces for uuid5. Changing them changes every derived id.
CHUNK_NAMESPACE = UUID("6f1c2b8e-3d4a-4f5b-9c6d-7e8f9a0b1c2d")
PIPELINE_CONFIG_NAMESPACE = UUID("0b6e3c1a-8f2d-4e7b-a5c9-d1e2f3a4b5c6")


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """A rectangle on a page, in PDF points.

    With origin 'BOTTOMLEFT' (the PDF default) `top` is greater than `bottom`.
    """

    left: float
    top: float
    right: float
    bottom: float
    origin: str = "BOTTOMLEFT"


@dataclass(frozen=True, slots=True)
class ChunkSpan:
    """One element of the source document that a chunk contains.

    source_ref: the parser's reference to the element, for example '#/texts/12'.
    label: the element type, for example 'text', 'table' or 'section_header'.
    page_no: the 1-based page; None for formats without pages.
    char_start, char_end: where the element text is inside the chunk content; None
        if the parser split or changed the text, so it cannot be found exactly.

    Raise ValueError for a page below 1 or an incomplete or reversed range.
    """

    source_ref: str
    label: str
    page_no: int | None = None
    bbox: BoundingBox | None = None
    char_start: int | None = None
    char_end: int | None = None

    def __post_init__(self) -> None:
        if self.page_no is not None and self.page_no < 1:
            raise ValueError(f"page_no must be 1 or more, not {self.page_no}.")
        if (self.char_start is None) != (self.char_end is None):
            raise ValueError("char_start and char_end must be set together.")
        if self.char_start is not None and not 0 <= self.char_start <= self.char_end:
            raise ValueError(
                f"Invalid character range {self.char_start}..{self.char_end}."
            )


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    """A chunk as a chunker returns it, before it gets an id and an owner.

    Raise ValueError for blank content or a negative token count.
    """

    content: str
    token_count: int
    headings: tuple[str, ...] = ()
    spans: tuple[ChunkSpan, ...] = ()

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("A chunk must contain text.")
        if self.token_count < 0:
            raise ValueError("token_count must not be negative.")


@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    """How chunks were made: parser, version, tokenizer and parameters.

    Two configs with the same values have the same hash and id. A new parser
    version or parameter gives a new id, which marks older chunks as stale.
    """

    component: str
    component_version: str
    model: str | None = None
    parameters: Mapping[str, Any] = field(default_factory=dict)

    @property
    def config_hash(self) -> str:
        """SHA-256 hex digest of the canonical JSON of all values."""
        canonical = json.dumps(
            {
                "component": self.component,
                "component_version": self.component_version,
                "model": self.model,
                "parameters": dict(self.parameters),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(canonical.encode()).hexdigest()

    @property
    def config_id(self) -> UUID:
        """The deterministic id of this config in the pipeline_config table."""
        return uuid5(PIPELINE_CONFIG_NAMESPACE, f"chunking:{self.config_hash}")


@dataclass(frozen=True, slots=True)
class Chunk:
    """A stored chunk of one document of one tenant."""

    chunk_id: UUID
    document_id: UUID
    tenant_id: UUID
    config_id: UUID
    chunk_index: int
    content: str
    content_hash: str
    token_count: int
    headings: tuple[str, ...] = ()
    spans: tuple[ChunkSpan, ...] = ()
    created_at: datetime | None = None

    @property
    def page_start(self) -> int | None:
        """The first page of the chunk, or None if no span has a page."""
        pages = self._pages()
        return min(pages) if pages else None

    @property
    def page_end(self) -> int | None:
        """The last page of the chunk, or None if no span has a page."""
        pages = self._pages()
        return max(pages) if pages else None

    def _pages(self) -> list[int]:
        return [span.page_no for span in self.spans if span.page_no is not None]


def build_chunks(
    drafts: Iterable[ChunkDraft],
    *,
    document_id: UUID,
    tenant_id: UUID,
    config: ChunkingConfig,
) -> list[Chunk]:
    """Number the drafts in order and give each a deterministic id and a hash."""
    return [
        Chunk(
            chunk_id=uuid5(
                CHUNK_NAMESPACE, f"{document_id}:{config.config_hash}:{index}"
            ),
            document_id=document_id,
            tenant_id=tenant_id,
            config_id=config.config_id,
            chunk_index=index,
            content=draft.content,
            content_hash=sha256(draft.content.encode()).hexdigest(),
            token_count=draft.token_count,
            headings=draft.headings,
            spans=draft.spans,
        )
        for index, draft in enumerate(drafts)
    ]
