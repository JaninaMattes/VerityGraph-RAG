import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import HttpUrl, PostgresDsn, RedisDsn, SecretStr

from src.api.dependencies import (
    get_current_tenant_id,
    get_document_service,
    get_settings,
    get_tenant_service,
)
from src.domain.documents.service import DocumentService
from src.domain.tenants.service import TenantService
from src.infrastructure.workflow_execution.temporalio.activities import (
    IngestFileActivities,
)
from src.libs.core.config import Settings
from src.main import app

# ==========================================================
# 1. Data Fixtures
# ==========================================================


@pytest.fixture
def mock_tenant_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_document_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_document_name() -> str:
    return "contract.pdf"


@pytest.fixture
def mock_tenant_organisation() -> str:
    return "Test Organisation"


@pytest.fixture
def test_settings() -> Settings:
    """
    Provides a fully populated, safe Settings object for testing.
    Using a fixture allows other tests to inject this directly if needed.
    """
    return Settings(
        app_name="Graph RAG Backend",
        environment="testing",
        secret_key=SecretStr("test-secret-key-for-ci-only-32-chars!!"),
        redis_url=RedisDsn("redis://localhost:6379/0"),
        redis_password=SecretStr("test-pwd"),
        postgres_url=PostgresDsn("postgresql+asyncpg://test:test@localhost:5432/test"),
        minio_url="localhost:9000",
        minio_root_user=SecretStr("test-user"),
        minio_root_password=SecretStr("test-pwd"),
        minio_sse_customer_key=SecretStr("minio-sse-customer-test-key-32!!"),
        kafka_url="localhost:9092",
        kafka_bootstrap_servers="localhost:9092",
        temporal_url="localhost:7233",
        temporal_task_queue="test-queue",
        frontend_url=HttpUrl("http://localhost:3000"),
        dev_tenant_id="12te3456-7s89-12t3-a456-78c91cf2b34f",
    )


# ==========================================================
# 2. Dependency Overrides (The Core of FastAPI Testing)
# ==========================================================


@pytest.fixture(autouse=True)
def override_global_dependencies(test_settings: Settings):
    """
    Autouse fixture that applies global dependency overrides for ALL tests.
    This ensures no test accidentally reads the real .env file or hits real infrastructure.
    """
    # Clear cache to ensure a fresh start
    get_settings.cache_clear()

    # Override the settings dependency
    app.dependency_overrides[get_settings] = lambda: test_settings

    yield

    # Teardown: Clean up to prevent leakage between tests
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    """Provides an isolated AsyncClient for FastAPI testing."""
    # Setup AsyncClient with ASGI transport for in-process testing
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def doc_client(
    mock_document_service: AsyncMock, mock_tenant_id: uuid.UUID
) -> AsyncGenerator[AsyncClient]:
    """
    Provides an isolated AsyncClient for API testing.
    """

    async def override_get_tenant() -> uuid.UUID:
        return mock_tenant_id

    async def override_get_service() -> DocumentService:
        return mock_document_service

    # Apply route-specific overrides
    app.dependency_overrides[get_current_tenant_id] = override_get_tenant
    app.dependency_overrides[get_document_service] = override_get_service

    # Setup AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Override_global_dependencies handles clearing the overrides
    app.dependency_overrides.pop(get_current_tenant_id, None)
    app.dependency_overrides.pop(get_document_service, None)


@pytest_asyncio.fixture
async def tenant_client(
    mock_tenant_service: AsyncMock, mock_tenant_id: uuid.UUID
) -> AsyncGenerator[AsyncClient]:
    """
    Provides an isolated AsyncClient for API testing.
    """

    async def override_get_tenant() -> uuid.UUID:
        return mock_tenant_id

    async def override_get_tenant_service() -> TenantService:
        return mock_tenant_service

    # Apply route-specific overrides
    app.dependency_overrides[get_current_tenant_id] = override_get_tenant
    app.dependency_overrides[get_tenant_service] = override_get_tenant_service

    # Setup AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Cleanup dependency overrides to prevent test contamination
    app.dependency_overrides.pop(get_current_tenant_id, None)
    app.dependency_overrides.pop(get_tenant_service, None)


# ==========================================================
# 3. Domain & Infrastructure Mocks
# ==========================================================


@pytest_asyncio.fixture
def mock_document_service() -> AsyncMock:
    """
    spec=DocumentService ensures the mock raises an AttributeError
    if a test tries to call a method that doesn't exist on the real class.
    This prevents "phantom" tests that pass but test nothing.
    """
    return AsyncMock(spec=DocumentService)


@pytest_asyncio.fixture
def mock_tenant_service() -> AsyncMock:
    """
    spec=TenantService ensures the mock raises an AttributeError
    if a test tries to call a method that doesn't exist on the real class.
    This prevents "phantom" tests that pass but test nothing.
    """
    return AsyncMock(spec=TenantService)


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """
    Mocks the SQLAlchemy async session.
    """
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None
    return session


@pytest.fixture
def mock_session_factory(mock_db_session: AsyncMock) -> MagicMock:
    """
    Mocks the `async_sessionmaker`.
    """
    return MagicMock(return_value=mock_db_session)


@pytest.fixture
def activities(mock_session_factory: MagicMock) -> IngestFileActivities:
    """
    Instantiates the Temporal Activities class with all dependencies mocked.
    """
    # Local import prevents circular dependency issues and speeds up test collection
    from src.infrastructure.workflow_execution.temporalio.activities import (
        IngestFileActivities,
    )

    return IngestFileActivities(
        session_factory=mock_session_factory,
        storage=MagicMock(),
        ingestion_pipeline=MagicMock(),
    )


@pytest.fixture
def activity_context():
    """
    Mocks Temporal's global activity context.
    """
    target_module = "temporalio.activity"

    with (
        patch(f"{target_module}.info") as mock_info,
        patch(f"{target_module}.logger") as mock_logger,
    ):
        mock_info.return_value = MagicMock(
            workflow_run_id="test-run-abc", activity_id="activity-123"
        )
        yield mock_info, mock_logger
