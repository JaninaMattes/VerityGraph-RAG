"""Shared fixtures for all test suites.

The fixtures never touch real infrastructure: settings are built in memory and
services, sessions and storage clients are mocks.
"""

import uuid
from collections.abc import AsyncGenerator, Iterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import HttpUrl, PostgresDsn, SecretStr

from src.api.dependencies import (
    get_chunk_service,
    get_current_tenant_id,
    get_document_service,
    get_settings,
    get_tenant_service,
    get_user_service,
)
from src.domain.chunks.service import ChunkService
from src.domain.documents.dataclasses import StorageKey
from src.domain.documents.entities import DocumentEntity
from src.domain.documents.service import DocumentService
from src.domain.ingestions.entities import IngestionJobEntity
from src.domain.tenants.entities import TenantEntity
from src.domain.tenants.service import TenantService
from src.domain.users.entities import UserEntity
from src.domain.users.service import UserService
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
        secret_key=SecretStr("test-secret-key-for-ci-only-32-chars!!"),
        postgres_url=PostgresDsn("postgresql+asyncpg://test:test@localhost:5432/test"),
        minio_url="localhost:9000",
        minio_root_user=SecretStr("test-user"),
        minio_root_password=SecretStr("test-pwd"),
        kafka_bootstrap_servers="localhost:9092",
        temporal_url="localhost:7233",
        temporal_task_queue="test-queue",
        frontend_url=HttpUrl("http://localhost:3000"),
        dev_tenant_id="12bf3456-7d89-12d3-a456-78c91cf2b34f",
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
# 3. FastAPI dependency overrides
# ==========================================================


@pytest.fixture(autouse=True)
def override_global_dependencies(test_settings: Settings) -> Iterator[None]:
    """Use the test settings in every request and clear all overrides afterwards."""
    get_settings.cache_clear()
    app.dependency_overrides[get_settings] = lambda: test_settings
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    """An in-process HTTP client for the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
def mock_document_service() -> AsyncMock:
    """spec= makes the mock fail on methods that the real class does not have."""
    return AsyncMock(spec=DocumentService)


@pytest.fixture
def mock_chunk_service() -> AsyncMock:
    return AsyncMock(spec=ChunkService)


@pytest.fixture
def mock_tenant_service() -> AsyncMock:
    return AsyncMock(spec=TenantService)


@pytest.fixture
def mock_user_service() -> AsyncMock:
    return AsyncMock(spec=UserService)


@pytest.fixture
def api_overrides(
    mock_tenant_id: uuid.UUID,
    mock_document_service: AsyncMock,
    mock_chunk_service: AsyncMock,
    mock_tenant_service: AsyncMock,
    mock_user_service: AsyncMock,
) -> None:
    """Replace the current tenant and all services with mocks."""
    app.dependency_overrides[get_current_tenant_id] = lambda: mock_tenant_id
    app.dependency_overrides[get_document_service] = lambda: mock_document_service
    app.dependency_overrides[get_chunk_service] = lambda: mock_chunk_service
    app.dependency_overrides[get_tenant_service] = lambda: mock_tenant_service
    app.dependency_overrides[get_user_service] = lambda: mock_user_service


@pytest_asyncio.fixture
async def doc_client(api_overrides: None, client: AsyncClient) -> AsyncClient:
    return client


@pytest_asyncio.fixture
async def tenant_client(api_overrides: None, client: AsyncClient) -> AsyncClient:
    return client


@pytest_asyncio.fixture
async def user_client(api_overrides: None, client: AsyncClient) -> AsyncClient:
    return client


# ==========================================================
# 4. Infrastructure mocks
# ==========================================================


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """A mocked SQLAlchemy AsyncSession that also works as an async context manager."""
    session = AsyncMock()
    session.add = MagicMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None
    return session


@pytest.fixture
def mock_session_factory(mock_db_session: AsyncMock) -> MagicMock:
    """A mocked async_sessionmaker that returns mock_db_session."""
    return MagicMock(return_value=mock_db_session)
