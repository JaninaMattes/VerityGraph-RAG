"""End-to-end tests of the ingestion path with real components.

Real: the upload URL, MinIO and its upload event, the Kafka event handler, the
Temporal workflow and activities, Docling, Postgres and the chunk read path.
Replaced: Kafka (the test passes MinIO's event to the handler) and the Temporal
server (the time-skipping test server). Opt-in with `make test-e2e`; the first run
downloads the Docling models and the tokenizer.
"""

import os
import queue
import shutil
import threading
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from io import BytesIO
from typing import Any

import httpx
import pytest
import pytest_asyncio
from minio import Minio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from src.domain.chunks.entities import Chunk
from src.domain.chunks.service import ChunkService
from src.domain.documents.entities import DocumentEntity
from src.domain.documents.service import DocumentService
from src.infrastructure.database.postgres.models import IngestionJob, Tenant
from src.infrastructure.database.postgres.repositories.chunk import (
    PostgresChunkRepository,
)
from src.infrastructure.database.postgres.repositories.document import (
    PostgresDocumentRepository,
)
from src.infrastructure.message_broker.kafka.handler import MinioObjectCreatedHandler
from src.infrastructure.parsing.docling import DoclingChunker, create_docling_chunker
from src.infrastructure.storage.minio.storage import MinioStorage
from src.infrastructure.workflow_execution.temporalio.activities import (
    IngestFileActivities,
)
from src.infrastructure.workflow_execution.temporalio.workflows import (
    DocumentIngestionWorkflow,
    processing_task_queue,
)
from src.libs.enums.document import DocumentStatus
from src.libs.enums.ingestionjob import ProcessingStatus
from temporalio.client import Client, WorkflowFailureError
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from tests.e2e.conftest import MinioServer
from tests.integration.pdf import text_pdf

pytestmark = pytest.mark.skipif(
    not (os.environ.get("E2E") and shutil.which("docker")),
    reason="set E2E=1 and start Docker",
)

BUCKET = "files"
TASK_QUEUE = "e2e-ingestion"
EVENT_TIMEOUT_SECONDS = 30
MAX_BYTES = 10 * 1024 * 1024
PAGES = [
    ["Annual Report 2026", "", "Acme Corp invests in Globex Inc."],
    ["Risk Factors", "", "Competition from Globex Inc. may reduce margins."],
]


class UploadEvents:
    """Collects the 'object created' records that MinIO sends for the bucket.

    MinIO opens the event stream lazily, so `wait_until_listening` writes probe
    objects until one of them arrives; only then can no upload be missed.
    """

    def __init__(self, client: Minio) -> None:
        self._client = client
        self._records: queue.Queue[dict[str, Any]] = queue.Queue()
        # A daemon thread: the stream blocks until the container is removed.
        threading.Thread(target=self._listen, daemon=True).start()

    def _listen(self) -> None:
        try:
            with self._client.listen_bucket_notification(
                BUCKET, events=("s3:ObjectCreated:*",)
            ) as events:
                for event in events:
                    for record in event["Records"]:
                        self._records.put(record)
        except Exception:  # noqa: BLE001 - the stream breaks when MinIO stops
            return

    def wait_until_listening(self) -> None:
        for attempt in range(EVENT_TIMEOUT_SECONDS):
            key = f"probe/{uuid.uuid4()}"
            self._client.put_object(BUCKET, key, BytesIO(b"probe"), 5)
            try:
                self.next_for(key, timeout=1)
                return
            except queue.Empty:
                continue
        pytest.fail("MinIO sent no upload events.")

    def next_for(self, key: str, timeout: float = EVENT_TIMEOUT_SECONDS) -> dict:
        """Return the next record of `key`. Raise queue.Empty after the timeout."""
        while True:
            record = self._records.get(timeout=timeout)
            if record["s3"]["object"]["key"].endswith(key):
                return record


@pytest.fixture(scope="session")
def chunker() -> DoclingChunker:
    """The real Docling chunker, loaded once (its models are large)."""
    return create_docling_chunker(
        tokenizer_model="BAAI/bge-small-en-v1.5",
        max_tokens=512,
        do_ocr=False,
        max_pages=50,
        max_bytes=MAX_BYTES,
    )


@pytest.fixture
def storage(minio_server: MinioServer) -> MinioStorage:
    storage = MinioStorage(client=minio_server.client(), bucket_name=BUCKET)
    storage.create_bucket()
    return storage


@pytest.fixture
def events(storage: MinioStorage) -> UploadEvents:
    """A listener for MinIO's upload events that is ready before the test uploads."""
    events = UploadEvents(storage.client)
    events.wait_until_listening()
    return events


@pytest_asyncio.fixture
async def tenant_id(session_factory: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    tenant_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(Tenant(tenant_id=tenant_id, organisation="ACME"))
        await session.commit()
    return tenant_id


@pytest_asyncio.fixture
async def temporal(
    session_factory: async_sessionmaker[AsyncSession],
    storage: MinioStorage,
    chunker: DoclingChunker,
) -> AsyncIterator[Client]:
    """A Temporal client with the two workers of the real worker process."""
    activities = IngestFileActivities(
        session_factory, storage, chunker, max_file_bytes=MAX_BYTES
    )
    async with (
        await WorkflowEnvironment.start_time_skipping(
            data_converter=pydantic_data_converter
        ) as env,
        Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[DocumentIngestionWorkflow],
            activities=[
                activities.create_document_activity,
                activities.update_document_activity,
                activities.create_ingestion_job_activity,
                activities.update_ingestion_job_activity,
            ],
        ),
        Worker(
            env.client,
            task_queue=processing_task_queue(TASK_QUEUE),
            activities=[activities.process_document_activity],
            max_concurrent_activities=1,
        ),
    ):
        yield env.client


async def upload(
    content: bytes,
    tenant_id: uuid.UUID,
    storage: MinioStorage,
    events: UploadEvents,
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[uuid.UUID, dict[str, Any]]:
    """Upload `content` like a client does; return the document id and its event."""
    async with session_factory() as session:
        url = await DocumentService(
            storage, PostgresDocumentRepository(session)
        ).create_upload_url(tenant_id=tenant_id, filename="report.pdf")
    async with httpx.AsyncClient() as http:
        response = await http.put(
            url.url, content=content, headers=url.required_headers
        )
    assert response.status_code == 200, response.text
    return url.document_id, events.next_for(f"{url.document_id}.pdf")


async def ingest(client: Client, record: dict[str, Any], document_id: uuid.UUID):
    """Pass the event to the handler and wait for the workflow to finish."""
    await MinioObjectCreatedHandler(client, TASK_QUEUE).handle(record)
    await client.get_workflow_handle(f"ingestion-job-{document_id}").result(
        rpc_timeout=timedelta(minutes=5)
    )


async def stored(
    session_factory: async_sessionmaker[AsyncSession],
    document_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> tuple[DocumentEntity, list[IngestionJob], list[Chunk]]:
    """Return the document, its ingestion jobs and its chunks (via the read path)."""
    async with session_factory() as session:
        documents = PostgresDocumentRepository(session)
        document = await documents.get_one(document_id, tenant_id)
        jobs = list(
            await session.scalars(
                select(IngestionJob).where(IngestionJob.document_id == document_id)
            )
        )
        chunks = await ChunkService(
            documents, PostgresChunkRepository(session)
        ).list_for_document(document_id, tenant_id)
    return document, jobs, chunks


class TestIngestionPipeline:
    """An upload ends as chunks with page evidence, or as a recorded failure."""

    async def test_uploaded_pdf_is_chunked_into_postgres(
        self, tenant_id, storage, events, session_factory, temporal
    ):
        """
        GIVEN a tenant and a two-page PDF
        WHEN the client uploads it with the presigned URL
            AND the handler receives MinIO's upload event
            AND the worker runs the ingestion workflow with real Docling
        THEN the document is PROCESSED and its ingestion job COMPLETED
        AND the chunk read path returns each sentence with its page and box
        """
        document_id, record = await upload(
            text_pdf(PAGES), tenant_id, storage, events, session_factory
        )

        await ingest(temporal, record, document_id)

        document, jobs, chunks = await stored(session_factory, document_id, tenant_id)
        assert document.status is DocumentStatus.PROCESSED
        assert [job.status for job in jobs] == [ProcessingStatus.COMPLETED]
        found = {
            chunk.content[span.char_start : span.char_end]: span
            for chunk in chunks
            for span in chunk.spans
            if span.char_start is not None
        }
        assert found["Acme Corp invests in Globex Inc."].page_no == 1
        assert found["Competition from Globex Inc. may reduce margins."].page_no == 2
        assert all(span.bbox is not None for span in found.values())

    async def test_invalid_file_is_recorded_as_failed(
        self, tenant_id, storage, events, session_factory, temporal
    ):
        """
        GIVEN bytes that are not a PDF, uploaded as 'report.pdf'
        WHEN the upload is ingested
        THEN the workflow fails without retries
        AND the document and its job are FAILED, the job with the reason
        AND no chunks are stored
        """
        document_id, record = await upload(
            b"this is not a pdf", tenant_id, storage, events, session_factory
        )

        with pytest.raises(WorkflowFailureError):
            await ingest(temporal, record, document_id)

        document, jobs, chunks = await stored(session_factory, document_id, tenant_id)
        assert document.status is DocumentStatus.FAILED
        (job,) = jobs
        assert job.status is ProcessingStatus.FAILED
        assert job.error_message
        assert chunks == []

    async def test_duplicate_event_is_ingested_once(
        self, tenant_id, storage, events, session_factory, temporal
    ):
        """
        GIVEN one upload whose event Kafka delivers twice (at-least-once delivery)
        WHEN both deliveries reach the handler
        THEN one workflow runs: the document has one job and one set of chunks
        """
        document_id, record = await upload(
            text_pdf(PAGES), tenant_id, storage, events, session_factory
        )

        await MinioObjectCreatedHandler(temporal, TASK_QUEUE).handle(record)
        await ingest(temporal, record, document_id)

        _, jobs, chunks = await stored(session_factory, document_id, tenant_id)
        assert [job.status for job in jobs] == [ProcessingStatus.COMPLETED]
        indexes = [chunk.chunk_index for chunk in chunks]
        assert indexes == list(range(len(chunks))) and indexes
