from typing import Any

from src.domain.chunks.entities import BoundingBox, Chunk, ChunkingConfig, ChunkSpan
from src.infrastructure.database.postgres.models.chunk import (
    DocumentChunk,
    DocumentChunkSpan,
)
from src.infrastructure.database.postgres.models.pipeline import PipelineConfig
from src.libs.enums.pipeline import PipelineKind


class ChunkMapper:
    """Converts chunks with their spans, and chunking configs, to rows and back."""

    @staticmethod
    def to_model(chunk: Chunk) -> DocumentChunk:
        """Return the row with its span rows. created_at is left to the database."""
        return DocumentChunk(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            tenant_id=chunk.tenant_id,
            config_id=chunk.config_id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            content_hash=chunk.content_hash,
            token_count=chunk.token_count,
            headings=list(chunk.headings),
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            spans=[
                _span_to_model(index, span) for index, span in enumerate(chunk.spans)
            ],
        )

    @staticmethod
    def to_entity(model: DocumentChunk) -> Chunk:
        """Return the chunk. The page range is derived from the spans again."""
        return Chunk(
            chunk_id=model.chunk_id,
            document_id=model.document_id,
            tenant_id=model.tenant_id,
            config_id=model.config_id,
            chunk_index=model.chunk_index,
            content=model.content,
            content_hash=model.content_hash,
            token_count=model.token_count,
            headings=tuple(model.headings),
            spans=tuple(_span_to_entity(span) for span in model.spans),
            created_at=model.created_at,
        )

    @staticmethod
    def config_to_model(config: ChunkingConfig) -> PipelineConfig:
        return PipelineConfig(**ChunkMapper.config_values(config))

    @staticmethod
    def config_values(config: ChunkingConfig) -> dict[str, Any]:
        """Return the column values of the pipeline_config row for `config`."""
        return {
            "config_id": config.config_id,
            "kind": PipelineKind.CHUNKING,
            "component": config.component,
            "component_version": config.component_version,
            "model": config.model,
            "parameters": dict(config.parameters),
            "config_hash": config.config_hash,
        }


def _span_to_model(index: int, span: ChunkSpan) -> DocumentChunkSpan:
    bbox = span.bbox
    return DocumentChunkSpan(
        span_index=index,
        source_ref=span.source_ref,
        label=span.label,
        page_no=span.page_no,
        bbox_left=bbox.left if bbox else None,
        bbox_top=bbox.top if bbox else None,
        bbox_right=bbox.right if bbox else None,
        bbox_bottom=bbox.bottom if bbox else None,
        bbox_origin=bbox.origin if bbox else None,
        char_start=span.char_start,
        char_end=span.char_end,
    )


def _span_to_entity(model: DocumentChunkSpan) -> ChunkSpan:
    bbox = None
    if model.bbox_origin is not None:
        bbox = BoundingBox(
            left=model.bbox_left,
            top=model.bbox_top,
            right=model.bbox_right,
            bottom=model.bbox_bottom,
            origin=model.bbox_origin,
        )
    return ChunkSpan(
        source_ref=model.source_ref,
        label=model.label,
        page_no=model.page_no,
        bbox=bbox,
        char_start=model.char_start,
        char_end=model.char_end,
    )
