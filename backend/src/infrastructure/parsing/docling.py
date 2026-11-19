"""DocumentChunker adapter: Docling parses the file, its HybridChunker splits it.

Docling needs the 'ingestion' extra (it pulls in torch). Only the ingestion worker
imports this module; the API does not.
"""

import threading
from collections.abc import Iterator
from importlib.metadata import version
from pathlib import Path
from typing import Any

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.exceptions import ConversionError
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from docling_core.types.doc.document import DoclingDocument

from src.domain.chunks.chunker import DocumentChunker
from src.domain.chunks.entities import (
    BoundingBox,
    ChunkDraft,
    ChunkingConfig,
    ChunkSpan,
)
from src.libs.exceptions.exceptions import DocumentParsingException

COMPONENT = "docling-hybrid-chunker"


class DoclingChunker(DocumentChunker):
    """Chunks a file with Docling. Each chunk keeps the page and box of its items."""

    def __init__(
        self,
        converter: Any,
        chunker: Any,
        config: ChunkingConfig,
        *,
        max_pages: int,
        max_bytes: int,
    ) -> None:
        self._converter = converter
        self._chunker = chunker
        self.config = config
        # Docling rejects a larger file before it runs a model (ConversionError).
        self.max_pages = max_pages
        self.max_bytes = max_bytes
        # Docling does not document its models as thread-safe: one file at a time.
        self._lock = threading.Lock()

    def chunk(self, file_path: Path) -> list[ChunkDraft]:
        """Return the non-blank chunks of the file in reading order.

        Raise DocumentParsingException if Docling cannot convert the file, or if
        it has more than `max_pages` pages or `max_bytes` bytes.
        """
        with self._lock:
            try:
                document = self._converter.convert(
                    file_path,
                    max_num_pages=self.max_pages,
                    max_file_size=self.max_bytes,
                ).document
            except ConversionError as exc:
                raise DocumentParsingException(
                    f"Docling cannot convert '{file_path.name}': {exc}"
                ) from exc
            return [
                ChunkDraft(
                    content=chunk.text,
                    token_count=self._chunker.tokenizer.count_tokens(chunk.text),
                    headings=tuple(chunk.meta.headings or ()),
                    spans=tuple(_spans(chunk, document)),
                )
                for chunk in self._chunker.chunk(document)
                if chunk.text.strip()
            ]


def _spans(chunk: Any, document: DoclingDocument) -> Iterator[ChunkSpan]:
    """Yield one span per page location of each document item in the chunk.

    The character range is where the item text occurs in the chunk text, searched
    in order. It is None if the chunker split or changed the item text.
    """
    cursor = 0
    for item in chunk.meta.doc_items:
        char_start = char_end = None
        text = getattr(item.get_ref().resolve(document), "text", None)
        if text and (found := chunk.text.find(text, cursor)) >= 0:
            char_start, char_end = found, found + len(text)
            cursor = char_end
        location = {
            "source_ref": item.self_ref,
            "label": item.label.value,
            "char_start": char_start,
            "char_end": char_end,
        }
        if not item.prov:
            yield ChunkSpan(**location)
        for prov in item.prov:
            box = prov.bbox
            yield ChunkSpan(
                **location,
                page_no=prov.page_no,
                bbox=BoundingBox(box.l, box.t, box.r, box.b, box.coord_origin.value),
            )


def create_docling_chunker(
    tokenizer_model: str, max_tokens: int, do_ocr: bool, max_pages: int, max_bytes: int
) -> DoclingChunker:
    """Build the chunker and the config that identifies its output.

    `tokenizer_model` should be the tokenizer of the embedding model, so a chunk
    never exceeds the embedding input. The tokenizer is downloaded once from
    Hugging Face; the Docling layout models are downloaded on the first file.
    """
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=PdfPipelineOptions(do_ocr=do_ocr)
            )
        }
    )
    tokenizer = HuggingFaceTokenizer.from_pretrained(
        model_name=tokenizer_model, max_tokens=max_tokens
    )
    config = ChunkingConfig(
        component=COMPONENT,
        component_version=version("docling"),
        model=tokenizer_model,
        parameters={
            "max_tokens": max_tokens,
            "merge_peers": True,
            "do_ocr": do_ocr,
            "docling_core": version("docling-core"),
        },
    )
    return DoclingChunker(
        converter=converter,
        chunker=HybridChunker(tokenizer=tokenizer, merge_peers=True),
        config=config,
        max_pages=max_pages,
        max_bytes=max_bytes,
    )
