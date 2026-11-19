"""Chunker port: turns a source file into chunk drafts with evidence spans."""

from pathlib import Path
from typing import Protocol

from src.domain.chunks.entities import ChunkDraft, ChunkingConfig


class DocumentChunker(Protocol):
    """Parses a file and splits it into chunks (for example Docling).

    `config` identifies the parser, its version and its parameters.
    """

    config: ChunkingConfig

    def chunk(self, file_path: Path) -> list[ChunkDraft]:
        """Return the chunks of the file in reading order.

        Blocking: async callers run it with asyncio.to_thread. Raise
        DocumentParsingException if the file is corrupt or has an unsupported format.
        """
        raise NotImplementedError
