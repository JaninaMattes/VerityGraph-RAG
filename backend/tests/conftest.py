"""Shared fixtures for all test suites.

The fixtures never touch real infrastructure: settings are built in memory and
services, sessions and storage clients are mocks.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import HttpUrl, PostgresDsn, SecretStr

from src.api.dependencies import get_settings
from src.domain.documents.dataclasses import StorageKey
from src.domain.documents.entities import DocumentEntity
from src.domain.ingestions.entities import IngestionJobEntity
from src.domain.tenants.entities import TenantEntity
from src.domain.users.entities import UserEntity
from src.libs.core.config import Settings
from src.libs.enums.document import DocumentStatus, DocumentType
from src.libs.enums.ingestionjob import IngestionStage, ProcessingStatus
from src.libs.enums.storage import StorageType
from src.libs.enums.tenant import TenantStatus
from src.libs.enums.user import UserRole, UserStatus
from src.main import app

# ==========================================================
# 1. Data fixtures
# ==========================================================


@pytest.fixture
def mock_tenant_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_document_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_document_name() -> str:
    return "contract.pdf"


@pytest.fixture
def mock_tenant_organisation() -> str:
    return "Test Organisation"


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)


@pytest.fixture
def test_settings() -> Settings:
    """A complete, safe Settings object that never reads the local .env file."""
    return Settings(
        app_name="Graph RAG Backend",
        environment="testing",
        secret_key=SecretStr("test-secret-key-for-unit-tests-only-" + "x" * 30),
        postgres_url=PostgresDsn("postgresql+asyncpg://test:test@localhost:5432/test"),
        minio_url="localhost:9000",
        minio_root_user=SecretStr("test-user"),
        minio_root_password=SecretStr("test-pwd"),
        kafka_bootstrap_servers="localhost:9092",
        temporal_url="localhost:7233",
        temporal_task_queue="test-queue",
        frontend_url=HttpUrl("http://localhost:3000"),
    )


# ==========================================================
# 2. Domain entity fixtures
# ==========================================================


@pytest.fixture
def document_entity(
    mock_document_id: uuid.UUID, mock_tenant_id: uuid.UUID, now: datetime
) -> DocumentEntity:
    return DocumentEntity(
        document_id=mock_document_id,
        tenant_id=mock_tenant_id,
        filename="contract.pdf",
        mime_type="application/pdf",
        document_type=DocumentType.PDF,
        bucket_name="files",
        storage_key=StorageKey(
            f"{mock_tenant_id}/files/2026/01/{mock_document_id}.pdf"
        ),
        storage_type=StorageType.MINIO,
        status=DocumentStatus.UPLOADED,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def job_entity(mock_document_id: uuid.UUID, now: datetime) -> IngestionJobEntity:
    return IngestionJobEntity(
        job_id=uuid.uuid4(),
        document_id=mock_document_id,
        workflow_id="ingestion-job-1",
        workflow_run_id="run-1",
        current_stage=IngestionStage.INITIALISING,
        status=ProcessingStatus.PENDING,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def tenant_entity(
    mock_tenant_id: uuid.UUID, mock_tenant_organisation: str, now: datetime
) -> TenantEntity:
    return TenantEntity(
        tenant_id=mock_tenant_id,
        organisation=mock_tenant_organisation,
        created_at=now,
        updated_at=now,
        status=TenantStatus.CREATED,
    )


@pytest.fixture
def user_entity(
    mock_user_id: uuid.UUID, mock_tenant_id: uuid.UUID, now: datetime
) -> UserEntity:
    return UserEntity(
        user_id=mock_user_id,
        tenant_id=mock_tenant_id,
        username="ada",
        email="ada@example.com",
        roles=[UserRole.USER],
        created_at=now,
        updated_at=now,
        status=UserStatus.CREATED,
    )


# ==========================================================
# 3. FastAPI settings (the API fixtures are in tests/api/conftest.py)
# ==========================================================


@pytest.fixture(autouse=True)
def override_global_dependencies(test_settings: Settings) -> Iterator[None]:
    """Use the test settings in every request and clear all overrides afterwards."""
    get_settings.cache_clear()
    app.dependency_overrides[get_settings] = lambda: test_settings
    yield
    app.dependency_overrides.clear()


# ==========================================================
# 4. Infrastructure mocks
# ==========================================================


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """A mocked SQLAlchemy AsyncSession that also works as an async context manager."""
    session = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()  # synchronous on a real AsyncSession
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None
    return session


@pytest.fixture
def mock_session_factory(mock_db_session: AsyncMock) -> MagicMock:
    """A mocked async_sessionmaker that returns mock_db_session."""
    return MagicMock(return_value=mock_db_session)
