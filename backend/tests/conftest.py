import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from src.api.dependencies import get_current_tenant_id, get_document_service
from src.domain.documents.service import DocumentService
from src.libs.core.config import get_settings
from src.main import app


# ------------------------------------------------------
# 1. Data Fixtures
# ------------------------------------------------------
@pytest.fixture
def mock_tenant_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_document_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_document_name() -> str:
    return "contract.pdf"


# ------------------------------------------------------
# 2. Dependency Mocks
# ------------------------------------------------------
@pytest.fixture(autouse=True)
def override_settings_for_tests(monkeypatch):
    # Clear the cache so it re-evaluates with test environment variables
    get_settings.cache_clear()


# Mock Domain Service
@pytest_asyncio.fixture
def mock_document_service() -> AsyncMock:
    # spec=DocumentService ensures the mock only allows valid methods
    return AsyncMock(spec=DocumentService)


@pytest_asyncio.fixture
async def client(
    mock_document_service: AsyncMock, mock_tenant_id: uuid.UUID
) -> AsyncGenerator[AsyncClient, None]:

    # Define overrides that capture the tenant_id
    async def override_get_tenant() -> uuid.UUID:
        return mock_tenant_id

    async def override_get_service() -> DocumentService:
        return mock_document_service

    # Apply overrides
    app.dependency_overrides[get_current_tenant_id] = override_get_tenant
    app.dependency_overrides[get_document_service] = override_get_service

    # Setup AsyncClient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Teardown: Clean up overrides to prevent leakage between tests
    app.dependency_overrides.clear()


# ------------------------------------------------------
# 4. Temporal Fixtures
# ------------------------------------------------------


@pytest.fixture
def mock_db_session():
    """
    Mocks the SQLAlchemy async session.
    We use AsyncMock so it can handle `await session.commit()`.
    """
    session = AsyncMock()
    # Configure async context manager (`async with session_factory() as session:`)
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None
    return session


@pytest.fixture
def mock_session_factory(mock_db_session):
    """
    Mocks the `async_sessionmaker`. Calling it should return the mock session.
    """
    return MagicMock(return_value=mock_db_session)


@pytest.fixture
def activities(mock_session_factory):
    """
    Instantiates the IngestFileActivities class with all its dependencies mocked out.
    """
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
    Mocks Temporal's global activity context (`activity.info()` and `activity.logger`).
    This avoids the need for a running Temporal server just to test the Python logic.
    """
    with (
        patch("temporalio.activity.info") as mock_info,
        patch("temporalio.activity.logger") as mock_logger,
    ):
        mock_info.return_value = MagicMock(
            workflow_run_id="test-run-abc", activity_id="activity-123"
        )
        yield mock_info, mock_logger
