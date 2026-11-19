"""Tests for the Docling chunker adapter.

The tests build real docling-core documents and chunks, but replace the converter
(layout models) and the tokenizer (Hugging Face download) with fakes.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from docling.exceptions import ConversionError
from docling_core.transforms.chunker.doc_chunk import DocChunk, DocMeta
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.transforms.chunker.tokenizer.base import BaseTokenizer
from docling_core.types.doc.base import BoundingBox, CoordOrigin
from docling_core.types.doc.common.reference import ProvenanceItem
from docling_core.types.doc.document import DoclingDocument
from docling_core.types.doc.labels import DocItemLabel

from src.domain.chunks.entities import BoundingBox as DomainBox
from src.domain.chunks.entities import ChunkingConfig
from src.infrastructure.parsing import docling as module
from src.infrastructure.parsing.docling import DoclingChunker, create_docling_chunker
from src.libs.exceptions.exceptions import DocumentParsingException

CONFIG = ChunkingConfig(component="docling-hybrid-chunker", component_version="1")


def prov(
    page_no: int, length: int, origin: CoordOrigin = CoordOrigin.BOTTOMLEFT
) -> ProvenanceItem:
    return ProvenanceItem(
        page_no=page_no,
        bbox=BoundingBox(l=72, t=728.5, r=180, b=717.5, coord_origin=origin),
        charspan=(0, length),
    )


class WordTokenizer(BaseTokenizer):
    """Counts words, so the real HybridChunker runs without a model download."""

    max_tokens: int

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    def get_max_tokens(self) -> int:
        return self.max_tokens

    def get_tokenizer(self) -> Any:
        # semchunk splits long items with it; a callable is used as token counter.
        return self.count_tokens


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

    def test_item_on_two_pages_has_one_span_per_page(self):
        """
        GIVEN an item that continues from page 1 to page 2
        WHEN the file is chunked
        THEN it becomes two spans, one per page, with the same character range
        """
        doc = DoclingDocument(name="split")
        item = doc.add_text(label=DocItemLabel.TEXT, text="Long text.", prov=prov(1, 4))
        item.prov.append(prov(2, 6))
        chunk = DocChunk(text="Long text.", meta=DocMeta(doc_items=[item]))

        (draft,) = make_chunker(doc, [chunk]).chunk(Path("a.pdf"))

        assert [(s.page_no, s.char_start, s.char_end) for s in draft.spans] == [
            (1, 0, 10),
            (2, 0, 10),
        ]

    def test_item_without_text_keeps_page_but_has_no_char_range(self):
        """
        GIVEN a picture item, which has no text
        WHEN the file is chunked
        THEN its span has the label, page and box but no character range
        """
        doc = DoclingDocument(name="figure")
        picture = doc.add_picture(prov=prov(3, 0))
        chunk = DocChunk(text="Figure 1", meta=DocMeta(doc_items=[picture]))

        (draft,) = make_chunker(doc, [chunk]).chunk(Path("a.pdf"))

        (only,) = draft.spans
        assert (only.source_ref, only.label, only.page_no) == (
            "#/pictures/0",
            "picture",
            3,
        )
        assert only.bbox is not None
        assert (only.char_start, only.char_end) == (None, None)

    def test_item_with_empty_text_has_no_char_range(self):
        """
        GIVEN an item with empty text
        WHEN the file is chunked
        THEN its span has no character range (not a zero-length one)
        """
        doc = DoclingDocument(name="empty")
        empty = doc.add_text(label=DocItemLabel.TEXT, text="", prov=prov(1, 0))
        chunk = DocChunk(text="Other text.", meta=DocMeta(doc_items=[empty]))

        (draft,) = make_chunker(doc, [chunk]).chunk(Path("a.pdf"))

        (only,) = draft.spans
        assert (only.char_start, only.char_end) == (None, None)

    def test_top_left_origin_is_kept(self):
        """
        GIVEN an item whose box uses the TOPLEFT origin (for example from an image)
        WHEN the file is chunked
        THEN the span box keeps the TOPLEFT origin and the coordinates unchanged
        """
        doc = DoclingDocument(name="scan")
        doc.add_text(
            label=DocItemLabel.TEXT,
            text="Scanned.",
            prov=prov(1, 8, origin=CoordOrigin.TOPLEFT),
        )
        chunk = DocChunk(text="Scanned.", meta=DocMeta(doc_items=list(doc.texts)))

        (draft,) = make_chunker(doc, [chunk]).chunk(Path("a.png"))

        assert draft.spans[0].bbox == DomainBox(72, 728.5, 180, 717.5, "TOPLEFT")

    def test_chunks_keep_order_and_search_each_chunk_from_its_start(self, document):
        """
        GIVEN two chunks with one item each
        WHEN the file is chunked
        THEN the drafts keep the chunk order
        AND the character range of each item is relative to its own chunk
        """
        heading, sentence = document.texts
        chunks = [
            DocChunk(text=heading.text, meta=DocMeta(doc_items=[heading])),
            DocChunk(text=sentence.text, meta=DocMeta(doc_items=[sentence])),
        ]

        drafts = make_chunker(document, chunks).chunk(Path("a.pdf"))

        assert [d.content for d in drafts] == [heading.text, sentence.text]
        assert [d.spans[0].char_start for d in drafts] == [0, 0]

    def test_chunk_without_headings_has_empty_headings(self, document):
        """
        GIVEN a chunk without headings
        WHEN the file is chunked
        THEN the draft has an empty headings tuple
        """
        sentence = document.texts[1]
        chunk = DocChunk(text=sentence.text, meta=DocMeta(doc_items=[sentence]))

        (draft,) = make_chunker(document, [chunk]).chunk(Path("a.pdf"))

        assert draft.headings == ()

    def test_converter_receives_the_file_path(self, document):
        """
        GIVEN a chunker
        WHEN a file is chunked
        THEN the converter is called once with that file path
        """
        chunker = make_chunker(document, [])

        chunker.chunk(Path("/tmp/report.pdf"))

        chunker._converter.convert.assert_called_once_with(Path("/tmp/report.pdf"))

    def test_other_errors_are_not_wrapped(self, document):
        """
        GIVEN the converter fails with an error that is not a ConversionError
        WHEN the file is chunked
        THEN the error is raised unchanged, so the activity can retry it
        """
        chunker = make_chunker(document, [])
        chunker._converter.convert.side_effect = OSError("disk full")

        with pytest.raises(OSError, match="disk full"):
            chunker.chunk(Path("a.pdf"))

    def test_concurrent_calls_convert_one_file_at_a_time(self, document):
        """
        GIVEN one chunker shared by two threads
        WHEN both threads chunk a file at the same time
        THEN the conversions do not overlap
        """
        active = peak = 0
        counter = threading.Lock()

        def slow_convert(_path: Path) -> SimpleNamespace:
            nonlocal active, peak
            with counter:
                active += 1
                peak = max(peak, active)
            time.sleep(0.05)
            with counter:
                active -= 1
            return SimpleNamespace(document=document)

        chunker = make_chunker(document, [])
        chunker._converter.convert.side_effect = slow_convert

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(chunker.chunk, [Path("a.pdf"), Path("b.pdf")]))

        assert peak == 1


class TestWithHybridChunker:
    """The adapter with the real HybridChunker and a word-counting tokenizer."""

    @staticmethod
    def real_chunker(document: DoclingDocument, max_tokens: int) -> DoclingChunker:
        converter = MagicMock()
        converter.convert.return_value = SimpleNamespace(document=document)
        hybrid = HybridChunker(
            tokenizer=WordTokenizer(max_tokens=max_tokens), merge_peers=True
        )
        return DoclingChunker(converter=converter, chunker=hybrid, config=CONFIG)

    def test_sections_give_headings_and_exact_char_ranges(self):
        """
        GIVEN a document with two sections on two pages
        WHEN the real HybridChunker chunks it
        THEN each sentence is in a chunk whose headings name its section
        AND its span has its page and the exact character range of its text
        """
        doc = DoclingDocument(name="report")
        sections = [
            ("Investments", "Acme Corp invests in Globex Inc.", 1),
            ("Risks", "Competition may reduce margins.", 2),
        ]
        for heading, sentence, page in sections:
            doc.add_heading(text=heading, prov=prov(page, len(heading)))
            doc.add_text(
                label=DocItemLabel.TEXT, text=sentence, prov=prov(page, len(sentence))
            )

        drafts = self.real_chunker(doc, max_tokens=64).chunk(Path("a.pdf"))

        found = {
            draft.content[span.char_start : span.char_end]: (draft.headings, span)
            for draft in drafts
            for span in draft.spans
            if span.char_start is not None
        }
        for heading, sentence, page in sections:
            headings, span = found[sentence]
            assert headings == (heading,)
            assert span.page_no == page

    def test_small_token_limit_splits_a_long_item(self):
        """
        GIVEN a paragraph of 12 words and a limit of 5 tokens
        WHEN the real HybridChunker chunks it
        THEN there is more than one chunk and no chunk exceeds the limit
        AND each piece keeps the page of the paragraph but has no character range
        """
        doc = DoclingDocument(name="long")
        text = "one two three four five six seven eight nine ten eleven twelve"
        doc.add_text(label=DocItemLabel.TEXT, text=text, prov=prov(4, len(text)))

        drafts = self.real_chunker(doc, max_tokens=5).chunk(Path("a.pdf"))

        assert len(drafts) > 1
        assert all(d.token_count <= 5 for d in drafts)
        assert " ".join(d.content for d in drafts) == text
        spans = [span for d in drafts for span in d.spans]
        assert all(s.page_no == 4 for s in spans)
        assert all(s.char_start is None for s in spans)


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

    @staticmethod
    def build(max_tokens: int = 256, do_ocr: bool = False) -> tuple[Any, Any, Any]:
        """Create the chunker with patched tokenizer and HybridChunker classes."""
        with (
            patch.object(module, "HuggingFaceTokenizer") as tokenizer_cls,
            patch.object(module, "HybridChunker") as hybrid_cls,
        ):
            chunker = create_docling_chunker(
                tokenizer_model="BAAI/bge-small-en-v1.5",
                max_tokens=max_tokens,
                do_ocr=do_ocr,
            )
        return chunker, tokenizer_cls, hybrid_cls

    def test_hybrid_chunker_gets_tokenizer_and_merges_peers(self):
        """
        GIVEN default settings
        WHEN the chunker is created
        THEN HybridChunker gets the loaded tokenizer and merge_peers=True
        AND the config records merge_peers and the docling-core version
        """
        chunker, tokenizer_cls, hybrid_cls = self.build()

        hybrid_cls.assert_called_once_with(
            tokenizer=tokenizer_cls.from_pretrained.return_value, merge_peers=True
        )
        assert chunker.config.parameters["merge_peers"] is True
        assert chunker.config.parameters["docling_core"] == module.version(
            "docling-core"
        )

    def test_ocr_setting_reaches_pipeline_and_config(self):
        """
        GIVEN OCR switched on
        WHEN the chunker is created
        THEN the PDF pipeline runs OCR AND the config records it
        """
        chunker, _, _ = self.build(do_ocr=True)

        pdf_option = chunker._converter.format_to_options[module.InputFormat.PDF]
        assert pdf_option.pipeline_options.do_ocr is True
        assert chunker.config.parameters["do_ocr"] is True

    def test_config_id_is_stable_and_follows_settings(self):
        """
        GIVEN two chunkers with the same settings AND one with another token limit
        WHEN their config IDs are compared
        THEN the same settings give the same ID (restarts keep the chunk IDs)
        AND another token limit gives another ID
        """
        first, _, _ = self.build(max_tokens=256)
        again, _, _ = self.build(max_tokens=256)
        other, _, _ = self.build(max_tokens=512)

        assert first.config.config_id == again.config.config_id
        assert first.config.config_id != other.config.config_id
