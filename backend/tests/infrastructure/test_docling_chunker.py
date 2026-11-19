"""Tests for the Docling chunker adapter.

The tests build real docling-core documents and chunks, but replace the converter
(layout models) and the tokenizer (Hugging Face download) with fakes.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from docling.exceptions import ConversionError
from docling_core.transforms.chunker.doc_chunk import DocChunk, DocMeta
from docling_core.types.doc import (
    BoundingBox,
    CoordOrigin,
    DocItemLabel,
    DoclingDocument,
    ProvenanceItem,
)

from src.domain.chunks.entities import BoundingBox as DomainBox
from src.domain.chunks.entities import ChunkingConfig
from src.infrastructure.parsing import docling as module
from src.infrastructure.parsing.docling import DoclingChunker, create_docling_chunker
from src.libs.exceptions.exceptions import DocumentParsingException

CONFIG = ChunkingConfig(component="docling-hybrid-chunker", component_version="1")


def prov(page_no: int, length: int) -> ProvenanceItem:
    return ProvenanceItem(
        page_no=page_no,
        bbox=BoundingBox(
            l=72, t=728.5, r=180, b=717.5, coord_origin=CoordOrigin.BOTTOMLEFT
        ),
        charspan=(0, length),
    )


@pytest.fixture
def document() -> DoclingDocument:
    """A document with a heading and a sentence on page 1."""
    doc = DoclingDocument(name="report")
    for label, text in [
        (DocItemLabel.SECTION_HEADER, "Investments"),
        (DocItemLabel.TEXT, "Acme Corp invests in Globex Inc."),
    ]:
        doc.add_text(label=label, text=text, prov=prov(1, len(text)))
    return doc


def make_chunker(document: DoclingDocument, chunks: list[DocChunk]) -> DoclingChunker:
    converter = MagicMock()
    converter.convert.return_value = SimpleNamespace(document=document)
    hybrid = MagicMock()
    hybrid.chunk.return_value = chunks
    hybrid.tokenizer.count_tokens.side_effect = lambda text: len(text.split())
    return DoclingChunker(converter=converter, chunker=hybrid, config=CONFIG)


class TestChunk:
    """chunk() turns Docling chunks into drafts with evidence spans."""

    def test_chunk_maps_text_headings_tokens_and_spans(self, document):
        """
        GIVEN a Docling chunk with a heading and two document items
        WHEN the file is chunked
        THEN the draft keeps text, headings and token count
        AND every item becomes a span with page, box, label, reference and the
            character range of the item text inside the chunk text
        """
        text = "Investments\nAcme Corp invests in Globex Inc."
        chunk = DocChunk(
            text=text,
            meta=DocMeta(doc_items=list(document.texts), headings=["Investments"]),
        )

        (draft,) = make_chunker(document, [chunk]).chunk(Path("report.pdf"))

        assert draft.content == text
        assert draft.headings == ("Investments",)
        assert draft.token_count == 7  # the fake tokenizer counts words
        first, second = draft.spans
        assert (first.source_ref, first.label, first.page_no) == (
            "#/texts/0",
            "section_header",
            1,
        )
        assert first.bbox == DomainBox(72, 728.5, 180, 717.5, "BOTTOMLEFT")
        assert text[second.char_start : second.char_end] == document.texts[1].text

    def test_item_text_not_in_chunk_has_no_char_range(self, document):
        """
        GIVEN a chunk whose text does not contain the item text (for example a split item)
        WHEN the file is chunked
        THEN the span keeps page and box but has no character range
        """
        chunk = DocChunk(
            text="Acme Corp invests", meta=DocMeta(doc_items=[document.texts[1]])
        )

        (draft,) = make_chunker(document, [chunk]).chunk(Path("report.pdf"))

        (only,) = draft.spans
        assert only.page_no == 1
        assert (only.char_start, only.char_end) == (None, None)

    def test_repeated_item_text_is_found_in_order(self):
        """
        GIVEN two items with the same text in one chunk
        WHEN the file is chunked
        THEN the second span points to the second occurrence
        """
        doc = DoclingDocument(name="repeat")
        for _ in range(2):
            doc.add_text(label=DocItemLabel.TEXT, text="Same.", prov=prov(1, 5))
        chunk = DocChunk(text="Same.\nSame.", meta=DocMeta(doc_items=list(doc.texts)))

        (draft,) = make_chunker(doc, [chunk]).chunk(Path("a.pdf"))

        assert [(s.char_start, s.char_end) for s in draft.spans] == [(0, 5), (6, 11)]

    def test_item_without_provenance_has_one_span_without_page(self):
        """
        GIVEN an item without provenance (for example from a Markdown file)
        WHEN the file is chunked
        THEN it becomes one span without page and box
        """
        doc = DoclingDocument(name="md")
        doc.add_text(label=DocItemLabel.TEXT, text="Plain text.")
        chunk = DocChunk(text="Plain text.", meta=DocMeta(doc_items=list(doc.texts)))

        (draft,) = make_chunker(doc, [chunk]).chunk(Path("a.md"))

        (only,) = draft.spans
        assert (only.page_no, only.bbox, only.char_start) == (None, None, 0)

    def test_blank_chunks_are_skipped(self, document):
        """
        GIVEN Docling returns a chunk with only white space
        WHEN the file is chunked
        THEN no draft is made for it
        """
        blank = DocChunk(text="  ", meta=DocMeta(doc_items=[document.texts[0]]))

        assert make_chunker(document, [blank]).chunk(Path("a.pdf")) == []

    def test_conversion_error_becomes_parsing_exception(self, document):
        """
        GIVEN Docling cannot convert the file (corrupt or unsupported format)
        WHEN the file is chunked
        THEN DocumentParsingException is raised
        """
        chunker = make_chunker(document, [])
        chunker._converter.convert.side_effect = ConversionError("bad file")

        with pytest.raises(DocumentParsingException, match="a.pdf"):
            chunker.chunk(Path("a.pdf"))

    def test_config_is_exposed(self, document):
        """
        GIVEN a chunker with a config
        WHEN its config is read
        THEN it is the config from the constructor
        """
        assert make_chunker(document, []).config == CONFIG


class TestFactory:
    """create_docling_chunker wires converter, tokenizer and config."""

    def test_factory_builds_config_from_settings(self):
        """
        GIVEN a tokenizer model, a token limit and OCR switched off
        WHEN the chunker is created
        THEN the config names Docling, its version, the model and the parameters
        AND the PDF pipeline has OCR switched off
        """
        with (
            patch.object(module, "HuggingFaceTokenizer") as tokenizer_cls,
            patch.object(module, "HybridChunker") as hybrid_cls,
        ):
            chunker = create_docling_chunker(
                tokenizer_model="BAAI/bge-small-en-v1.5", max_tokens=256, do_ocr=False
            )

        tokenizer_cls.from_pretrained.assert_called_once_with(
            model_name="BAAI/bge-small-en-v1.5", max_tokens=256
        )
        hybrid_cls.assert_called_once()
        config = chunker.config
        assert config.component == "docling-hybrid-chunker"
        assert config.model == "BAAI/bge-small-en-v1.5"
        assert config.parameters["max_tokens"] == 256
        assert config.parameters["do_ocr"] is False
        assert config.component_version
        pdf_option = chunker._converter.format_to_options[module.InputFormat.PDF]
        assert pdf_option.pipeline_options.do_ocr is False
