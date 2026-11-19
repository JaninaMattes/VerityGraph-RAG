"""End-to-end test of the ingestion path with real components.

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
from datetime import timedelta
from io import BytesIO
from typing import Any

import httpx
import pytest
from minio import Minio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from src.domain.chunks.service import ChunkService
from src.domain.documents.service import DocumentService
from src.infrastructure.database.postgres.models import IngestionJob, Tenant
from src.infrastructure.database.postgres.repositories.chunk import (
    PostgresChunkRepository,
)
from src.infrastructure.database.postgres.repositories.document import (
    PostgresDocumentRepository,
)
from src.infrastructure.message_broker.kafka.handler import MinioObjectCreatedHandler
from src.infrastructure.parsing.docling import create_docling_chunker
from src.infrastructure.storage.minio.storage import MinioStorage
from src.infrastructure.workflow_execution.temporalio.activities import (
    IngestFileActivities,
)
from src.infrastructure.workflow_execution.temporalio.workflows import (
    DocumentIngestionWorkflow,
)
from src.libs.enums.document import DocumentStatus
from src.libs.enums.ingestionjob import ProcessingStatus
from tests.e2e.conftest import MinioServer
from tests.integration.pdf import text_pdf

pytestmark = pytest.mark.skipif(
    not (os.environ.get("E2E") and shutil.which("docker")),
    reason="set E2E=1 and start Docker",
)

BUCKET = "files"
TASK_QUEUE = "e2e-ingestion"
EVENT_TIMEOUT_SECONDS = 30
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
            key = f"probe/{attempt}"
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


async def add_tenant(session_factory: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    tenant_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(Tenant(tenant_id=tenant_id, organisation="ACME"))
        await session.commit()
    return tenant_id


class TestIngestionPipeline:
    """An uploaded PDF ends as chunks with page evidence in Postgres."""

    async def test_uploaded_pdf_is_chunked_into_postgres(
        self,
        minio_server: MinioServer,
        session_factory: async_sessionmaker[AsyncSession],
    ):
        """
        GIVEN a tenant, an empty bucket and a two-page PDF
        WHEN the client uploads the PDF with the presigned URL
            AND the handler receives MinIO's upload event
            AND the worker runs the ingestion workflow with real Docling
        THEN the workflow completes
        AND the document is PROCESSED and its ingestion job COMPLETED
        AND the chunk read path returns each sentence with its page and box
        """
        # Arrange
        client = minio_server.client()
        storage = MinioStorage(client=client, bucket_name=BUCKET)
        storage.create_bucket()
        events = UploadEvents(client)
        events.wait_until_listening()
        tenant_id = await add_tenant(session_factory)
        async with session_factory() as session:
            upload = await DocumentService(
                storage, PostgresDocumentRepository(session)
            ).create_upload_url(tenant_id=tenant_id, filename="report.pdf")
        chunker = create_docling_chunker(
            tokenizer_model="BAAI/bge-small-en-v1.5", max_tokens=512, do_ocr=False
        )
        activities = IngestFileActivities(session_factory, storage, chunker)

        # Act
        async with httpx.AsyncClient() as http:
            response = await http.put(
                upload.url, content=text_pdf(PAGES), headers=upload.required_headers
            )
        assert response.status_code == 200, response.text
        record = events.next_for(f"{upload.document_id}.pdf")
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
                    activities.process_document_activity,
                ],
            ),
        ):
            await MinioObjectCreatedHandler(env.client, TASK_QUEUE).handle(record)
            handle = env.client.get_workflow_handle(
                f"ingestion-job-{upload.document_id}"
            )
            await handle.result(rpc_timeout=timedelta(minutes=5))

        # Assert
        async with session_factory() as session:
            document = await PostgresDocumentRepository(session).get_one(
                upload.document_id, tenant_id
            )
            job = await session.scalar(
                select(IngestionJob).where(
                    IngestionJob.document_id == upload.document_id
                )
            )
            chunks = await ChunkService(
                PostgresDocumentRepository(session), PostgresChunkRepository(session)
            ).list_for_document(upload.document_id, tenant_id)
        assert document.status is DocumentStatus.PROCESSED
        assert job is not None and job.status is ProcessingStatus.COMPLETED
        found = {
            chunk.content[span.char_start : span.char_end]: span
            for chunk in chunks
            for span in chunk.spans
            if span.char_start is not None
        }
        assert found["Acme Corp invests in Globex Inc."].page_no == 1
        assert found["Competition from Globex Inc. may reduce margins."].page_no == 2
        assert all(span.bbox is not None for span in found.values())
