"""Tests for the Temporal ingestion activities.

Each activity must classify errors correctly: data errors and missing records are
non-retryable; database and storage faults are retryable.
"""

import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from src.domain.documents.entities import DocumentEntity
from src.domain.ingestions.entities import IngestionJobEntity
from src.infrastructure.workflow_execution.temporalio.activities import (
    IngestFileActivities,
)
from src.infrastructure.workflow_execution.temporalio.models import (
    CreateDocumentPayload,
    CreateIngestionJobPayload,
    ProcessDocumentPayload,
    UpdateDocumentPayload,
    UpdateIngestionJobPayload,
)
from src.libs.enums.document import DocumentStatus, DocumentType
from src.libs.enums.ingestionjob import IngestionStage, ProcessingStatus
from src.libs.enums.storage import StorageType
from src.libs.exceptions.exceptions import (
    AccessDeniedException,
    DatabaseInternalException,
    DocumentNotFoundException,
    IngestionJobNotFoundException,
    ObjectNotFoundException,
    StorageOperationException,
)

pytestmark = pytest.mark.asyncio

MODULE = "src.infrastructure.workflow_execution.temporalio.activities"
DOCUMENT_ID = "123e4567-e89b-12d3-a456-426614174000"
TENANT_ID = "123e4567-e89b-12d3-a456-426614174001"
JOB_ID = "123e4567-e89b-12d3-a456-426614174002"


@pytest.fixture
def storage() -> MagicMock:
    return MagicMock()


@pytest.fixture
def activities(
    mock_session_factory: MagicMock, storage: MagicMock
) -> IngestFileActivities:
    return IngestFileActivities(session_factory=mock_session_factory, storage=storage)


@pytest.fixture
def env() -> ActivityEnvironment:
    return ActivityEnvironment()


@pytest.fixture
def doc_repo() -> Iterator[AsyncMock]:
    repo = AsyncMock()
    with patch(f"{MODULE}.PostgresDocumentRepository", return_value=repo):
        yield repo


@pytest.fixture
def job_repo() -> Iterator[AsyncMock]:
    repo = AsyncMock()
    with patch(f"{MODULE}.PostgresIngestionJobRepository", return_value=repo):
        yield repo


def create_document_payload(**overrides: str) -> CreateDocumentPayload:
    values = {
        "document_id": DOCUMENT_ID,
        "tenant_id": TENANT_ID,
        "filename": "report.pdf",
        "bucket_name": "files",
        "storage_key": f"{TENANT_ID}/files/2026/01/{DOCUMENT_ID}.pdf",
        "document_type": "PDF",
        "status": "UPLOADED",
        "storage_type": "MINIO",
    }
    return CreateDocumentPayload(**(values | overrides))


def assert_non_retryable(exc: ApplicationError, error_type: str) -> None:
    assert exc.non_retryable is True
    assert exc.type == error_type


def assert_retryable(exc: ApplicationError) -> None:
    assert exc.non_retryable is False


class TestCreateDocumentActivity:
    """create_document_activity stores a new document record."""

    async def test_valid_payload_creates_and_commits(
        self, env, activities, doc_repo, mock_db_session
    ):
        """
        GIVEN a valid payload
        WHEN the activity runs
        THEN the repository receives an entity with the parsed enums
        AND the session commits once
        """
        await env.run(activities.create_document_activity, create_document_payload())

        entity: DocumentEntity = doc_repo.create.call_args.args[0]
        assert entity.document_id == uuid.UUID(DOCUMENT_ID)
        assert entity.document_type is DocumentType.PDF
        assert entity.status is DocumentStatus.UPLOADED
        assert entity.storage_type is StorageType.MINIO
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.parametrize(
        "overrides",
        [{"document_type": "EXE"}, {"status": "BROKEN"}, {"document_id": "not-a-uuid"}],
        ids=["bad-document-type", "bad-status", "bad-uuid"],
    )
    async def test_invalid_payload_is_non_retryable(
        self, env, activities, doc_repo, mock_db_session, overrides
    ):
        """
        GIVEN a payload with an invalid enum name or UUID
        WHEN the activity runs
        THEN it raises a non-retryable 'DataValidationFailure' AND commits nothing
        """
        with pytest.raises(ApplicationError) as exc_info:
            await env.run(
                activities.create_document_activity,
                create_document_payload(**overrides),
            )

        assert_non_retryable(exc_info.value, "DataValidationFailure")
        mock_db_session.commit.assert_not_awaited()

    async def test_database_error_is_retryable(self, env, activities, doc_repo):
        """
        GIVEN the repository fails with a database error
        WHEN the activity runs
        THEN it raises a retryable 'DatabaseFailure'
        """
        doc_repo.create.side_effect = DatabaseInternalException("db down")

        with pytest.raises(ApplicationError) as exc_info:
            await env.run(
                activities.create_document_activity, create_document_payload()
            )

        assert_retryable(exc_info.value)
        assert exc_info.value.type == "DatabaseFailure"


class TestUpdateDocumentActivity:
    """update_document_activity moves a document to a new status."""

    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            ("UPLOADED", DocumentStatus.UPLOADED),
            ("PROCESSED", DocumentStatus.PROCESSED),
            ("FAILED", DocumentStatus.FAILED),
        ],
    )
    async def test_status_transition_is_saved(
        self,
        env,
        activities,
        doc_repo,
        mock_db_session,
        document_entity,
        status,
        expected,
    ):
        """
        GIVEN an existing document
        WHEN the activity runs with a supported status
        THEN the document has the new status, size and bucket AND the session commits
        """
        doc_repo.get_one.return_value = document_entity
        payload = UpdateDocumentPayload(
            document_id=DOCUMENT_ID,
            tenant_id=TENANT_ID,
            size_bytes=2048,
            bucket_name="other-bucket",
            status=status,
        )

        await env.run(activities.update_document_activity, payload)

        doc_repo.get_one.assert_awaited_once_with(
            uuid.UUID(DOCUMENT_ID), uuid.UUID(TENANT_ID)
        )
        saved: DocumentEntity = doc_repo.update.call_args.args[0]
        assert saved.status is expected
        assert saved.size_bytes == 2048
        assert saved.bucket_name == "other-bucket"
        mock_db_session.commit.assert_awaited_once()

    async def test_unsupported_status_is_non_retryable(
        self, env, activities, doc_repo, mock_db_session
    ):
        """
        GIVEN a status that is not a supported transition
        WHEN the activity runs
        THEN it raises a non-retryable 'DataValidationFailure' AND reads nothing
        """
        payload = UpdateDocumentPayload(
            document_id=DOCUMENT_ID,
            tenant_id=TENANT_ID,
            size_bytes=1,
            bucket_name="files",
            status="UPLOAD_PENDING",
        )

        with pytest.raises(ApplicationError) as exc_info:
            await env.run(activities.update_document_activity, payload)

        assert_non_retryable(exc_info.value, "DataValidationFailure")
        doc_repo.get_one.assert_not_awaited()
        mock_db_session.commit.assert_not_awaited()

    async def test_missing_document_is_non_retryable(
        self, env, activities, doc_repo, mock_db_session
    ):
        """
        GIVEN the document does not exist
        WHEN the activity runs
        THEN it raises a non-retryable 'NotFound' AND commits nothing
        """
        doc_repo.get_one.side_effect = DocumentNotFoundException(uuid.UUID(DOCUMENT_ID))
        payload = UpdateDocumentPayload(
            document_id=DOCUMENT_ID,
            tenant_id=TENANT_ID,
            size_bytes=1,
            bucket_name="files",
            status="FAILED",
        )

        with pytest.raises(ApplicationError) as exc_info:
            await env.run(activities.update_document_activity, payload)

        assert_non_retryable(exc_info.value, "NotFound")
        doc_repo.update.assert_not_awaited()
        mock_db_session.commit.assert_not_awaited()


class TestCreateIngestionJobActivity:
    """create_ingestion_job_activity stores a new job record."""

    def payload(self, **overrides: str) -> CreateIngestionJobPayload:
        values = {
            "job_id": JOB_ID,
            "document_id": DOCUMENT_ID,
            "workflow_id": "wf",
            "workflow_run_id": "run",
        }
        return CreateIngestionJobPayload(**(values | overrides))

    async def test_valid_payload_creates_and_commits(
        self, env, activities, job_repo, mock_db_session
    ):
        """
        GIVEN a valid payload with the default stage and status
        WHEN the activity runs
        THEN the repository receives a PENDING job in stage INITIALISING AND the session commits
        """
        await env.run(activities.create_ingestion_job_activity, self.payload())

        job: IngestionJobEntity = job_repo.create.call_args.args[0]
        assert job.job_id == uuid.UUID(JOB_ID)
        assert job.current_stage is IngestionStage.INITIALISING
        assert job.status is ProcessingStatus.PENDING
        mock_db_session.commit.assert_awaited_once()

    async def test_invalid_stage_is_non_retryable(self, env, activities, job_repo):
        """
        GIVEN a payload with an unknown stage name
        WHEN the activity runs
        THEN it raises a non-retryable 'DataValidationFailure'
        """
        with pytest.raises(ApplicationError) as exc_info:
            await env.run(
                activities.create_ingestion_job_activity,
                self.payload(current_stage="NOPE"),
            )

        assert_non_retryable(exc_info.value, "DataValidationFailure")
        job_repo.create.assert_not_awaited()

    async def test_database_error_is_retryable(self, env, activities, job_repo):
        """
        GIVEN the repository fails with a database error
        WHEN the activity runs
        THEN it raises a retryable error
        """
        job_repo.create.side_effect = DatabaseInternalException("db down")

        with pytest.raises(ApplicationError) as exc_info:
            await env.run(activities.create_ingestion_job_activity, self.payload())

        assert_retryable(exc_info.value)


class TestUpdateIngestionJobActivity:
    """update_ingestion_job_activity moves a job to a new status."""

    def payload(
        self, status: str, error: str | None = None
    ) -> UpdateIngestionJobPayload:
        return UpdateIngestionJobPayload(
            job_id=JOB_ID, document_id=DOCUMENT_ID, status=status, error_message=error
        )

    async def test_completed_marks_job_completed(
        self, env, activities, job_repo, mock_db_session, job_entity
    ):
        """
        GIVEN an existing job
        WHEN the activity runs with status COMPLETED
        THEN the job is completed, has no stage and has a finish time
        """
        job_repo.get_one.return_value = job_entity

        await env.run(
            activities.update_ingestion_job_activity, self.payload("COMPLETED")
        )

        saved: IngestionJobEntity = job_repo.update.call_args.args[0]
        assert saved.status is ProcessingStatus.COMPLETED
        assert saved.current_stage is None
        assert saved.finished_at is not None
        mock_db_session.commit.assert_awaited_once()

    @pytest.mark.parametrize(
        ("error", "expected"),
        [("parser failed", "parser failed"), (None, "Unknown error")],
    )
    async def test_failed_records_error_message(
        self, env, activities, job_repo, job_entity, error, expected
    ):
        """
        GIVEN an existing job
        WHEN the activity runs with status FAILED and an optional error message
        THEN the job is failed with the message, or with 'Unknown error' if none is given
        """
        job_repo.get_one.return_value = job_entity

        await env.run(
            activities.update_ingestion_job_activity, self.payload("FAILED", error)
        )

        saved: IngestionJobEntity = job_repo.update.call_args.args[0]
        assert saved.status is ProcessingStatus.FAILED
        assert saved.error_message == expected

    async def test_other_status_is_set_directly(
        self, env, activities, job_repo, job_entity
    ):
        """
        GIVEN an existing job
        WHEN the activity runs with status RUNNING
        THEN the job status is RUNNING
        """
        job_repo.get_one.return_value = job_entity

        await env.run(activities.update_ingestion_job_activity, self.payload("RUNNING"))

        assert job_repo.update.call_args.args[0].status is ProcessingStatus.RUNNING

    async def test_invalid_status_is_non_retryable(
        self, env, activities, job_repo, job_entity
    ):
        """
        GIVEN an existing job
        WHEN the activity runs with an unknown status name
        THEN it raises a non-retryable 'DataValidationFailure'
        """
        job_repo.get_one.return_value = job_entity

        with pytest.raises(ApplicationError) as exc_info:
            await env.run(
                activities.update_ingestion_job_activity, self.payload("NOPE")
            )

        assert_non_retryable(exc_info.value, "DataValidationFailure")
        job_repo.update.assert_not_awaited()

    async def test_missing_job_is_non_retryable(self, env, activities, job_repo):
        """
        GIVEN the job does not exist
        WHEN the activity runs
        THEN it raises a non-retryable 'NotFound'
        """
        job_repo.get_one.side_effect = IngestionJobNotFoundException(uuid.UUID(JOB_ID))

        with pytest.raises(ApplicationError) as exc_info:
            await env.run(
                activities.update_ingestion_job_activity, self.payload("COMPLETED")
            )

        assert_non_retryable(exc_info.value, "NotFound")


class TestProcessDocumentActivity:
    """process_document_activity downloads the object to a safe temporary path."""

    def payload(self, filename: str = "report.pdf") -> ProcessDocumentPayload:
        return ProcessDocumentPayload(
            document_id=DOCUMENT_ID,
            filename=filename,
            bucket="files",
            object_key=f"{TENANT_ID}/files/2026/01/{DOCUMENT_ID}.pdf",
            etag="abc",
            size_bytes=1,
        )

    async def test_download_uses_object_key_name_not_client_filename(
        self, env, activities, storage
    ):
        """
        GIVEN a client filename that tries a path traversal ('../../evil.pdf')
        WHEN the activity runs
        THEN the local file is '<document_id>.pdf' inside a temporary directory
        AND the result reports the processed document
        """
        result = await env.run(
            activities.process_document_activity, self.payload("../../evil.pdf")
        )

        bucket, object_key, local_path = storage.download_object.call_args.args
        assert bucket == "files"
        assert object_key.endswith(f"{DOCUMENT_ID}.pdf")
        assert Path(local_path).name == f"{DOCUMENT_ID}.pdf"
        assert ".." not in Path(local_path).parts
        assert not os.path.exists(local_path)  # the temp directory is removed
        assert result.document_id == DOCUMENT_ID
        assert result.status == DocumentStatus.PROCESSED.value

    @pytest.mark.parametrize(
        "error",
        [
            ObjectNotFoundException("key", "files"),
            AccessDeniedException("files"),
            FileNotFoundError("gone"),
        ],
        ids=["missing-object", "access-denied", "missing-file"],
    )
    async def test_permanent_errors_are_non_retryable(
        self, env, activities, storage, error
    ):
        """
        GIVEN the download fails with an error that a retry cannot fix
        WHEN the activity runs
        THEN it raises a non-retryable 'ProcessingFailure'
        """
        storage.download_object.side_effect = error

        with pytest.raises(ApplicationError) as exc_info:
            await env.run(activities.process_document_activity, self.payload())

        assert_non_retryable(exc_info.value, "ProcessingFailure")

    async def test_transient_storage_error_is_retryable(self, env, activities, storage):
        """
        GIVEN the download fails with a transient storage error
        WHEN the activity runs
        THEN it raises a retryable 'ProcessingFailure'
        """
        storage.download_object.side_effect = StorageOperationException(
            "files", "timeout"
        )

        with pytest.raises(ApplicationError) as exc_info:
            await env.run(activities.process_document_activity, self.payload())

        assert_retryable(exc_info.value)
        assert exc_info.value.type == "ProcessingFailure"
