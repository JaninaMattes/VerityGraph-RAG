"""End-to-end test: real Docling chunks a PDF, Postgres stores the chunks.

Opt-in with DOCLING_INTEGRATION=1 (it downloads the Docling layout models and the
tokenizer, several hundred MB, on the first run) and TEST_DATABASE_URL.
"""

import os
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.domain.chunks.entities import build_chunks
from src.infrastructure.database.postgres.repositories.chunk import (
    PostgresChunkRepository,
)
from src.infrastructure.parsing.docling import create_docling_chunker
from tests.integration.pdf import text_pdf
from tests.integration.test_postgres_schema import add_document

pytestmark = pytest.mark.skipif(
    not (os.environ.get("DOCLING_INTEGRATION") and os.environ.get("TEST_DATABASE_URL")),
    reason="set DOCLING_INTEGRATION=1 and TEST_DATABASE_URL",
)

PAGES = [
    ["Annual Report 2026", "", "Acme Corp invests in Globex Inc."],
    ["Risk Factors", "", "Competition from Globex Inc. may reduce margins."],
]


async def test_uploaded_pdf_is_stored_with_page_evidence(
    session: AsyncSession, tmp_path: Path
):
    """
    GIVEN a two-page PDF
    WHEN real Docling chunks it AND the chunks are stored and read back
    THEN every sentence is in a stored chunk
    AND each sentence has a span with its page, a box and its place in the chunk
    """
    pdf = tmp_path / "report.pdf"
    pdf.write_bytes(text_pdf(PAGES))
    chunker = create_docling_chunker(
        tokenizer_model="BAAI/bge-small-en-v1.5", max_tokens=512, do_ocr=False
    )
    tenant_id, document_id = await add_document(session)

    chunks = build_chunks(
        chunker.chunk(pdf),
        document_id=document_id,
        tenant_id=tenant_id,
        config=chunker.config,
    )
    repository = PostgresChunkRepository(session)
    await repository.replace_for_document(
        document_id, tenant_id, chunker.config, chunks
    )
    await session.commit()
    stored = await repository.list_for_document(document_id, tenant_id)

    assert [c.chunk_id for c in stored] == [c.chunk_id for c in chunks]
    spans = {
        stored_chunk.content[span.char_start : span.char_end]: (span.page_no, span.bbox)
        for stored_chunk in stored
        for span in stored_chunk.spans
        if span.char_start is not None
    }
    assert spans["Acme Corp invests in Globex Inc."][0] == 1
    assert spans["Competition from Globex Inc. may reduce margins."][0] == 2
    assert all(bbox is not None for _, bbox in spans.values())
