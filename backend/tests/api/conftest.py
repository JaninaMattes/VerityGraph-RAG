"""Fixtures for the HTTP API tests.

Every service is a mock, so no request reaches real infrastructure. `client` sends
requests without a token; `api_client` sends them as `principal`, an admin of the
mock tenant; `as_member` turns that caller into a user without the admin role.
"""

import uuid
from collections.abc import AsyncGenerator
from dataclasses import replace
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import (
    get_auth_service,
    get_chunk_service,
    get_current_principal,
    get_document_service,
    get_login_rate_limiter,
    get_tenant_service,
    get_user_service,
)
from src.api.rate_limit import RateLimiter
from src.domain.auth.entities import Principal
from src.domain.auth.service import AuthService
from src.domain.chunks.service import ChunkService
from src.domain.documents.service import DocumentService
from src.domain.tenants.service import TenantService
from src.domain.users.service import UserService
from src.libs.enums.user import UserRole
from src.main import app


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
def mock_auth_service() -> AsyncMock:
    return AsyncMock(spec=AuthService)


@pytest.fixture
def login_limiter() -> RateLimiter:
    """A fresh login limiter per test, so the attempts of one test do not count in
    the next."""
    return RateLimiter(limit=3)


@pytest.fixture(autouse=True)
def mock_services(
    mock_document_service: AsyncMock,
    mock_chunk_service: AsyncMock,
    mock_tenant_service: AsyncMock,
    mock_user_service: AsyncMock,
    mock_auth_service: AsyncMock,
    login_limiter: RateLimiter,
) -> None:
    """Replace every service with its mock (the root conftest clears overrides)."""
    app.dependency_overrides.update(
        {
            get_document_service: lambda: mock_document_service,
            get_chunk_service: lambda: mock_chunk_service,
            get_tenant_service: lambda: mock_tenant_service,
            get_user_service: lambda: mock_user_service,
            get_auth_service: lambda: mock_auth_service,
            get_login_rate_limiter: lambda: login_limiter,
        }
    )


@pytest.fixture
def principal(mock_user_id: uuid.UUID, mock_tenant_id: uuid.UUID) -> Principal:
    """The default caller: an admin of the mock tenant."""
    return Principal(mock_user_id, mock_tenant_id, frozenset({UserRole.ADMIN}))


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    """An in-process HTTP client that sends no token."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http_client:
        yield http_client


@pytest.fixture
def api_client(client: AsyncClient, principal: Principal) -> AsyncClient:
    """The HTTP client, authenticated as `principal`."""
    app.dependency_overrides[get_current_principal] = lambda: principal
    return client


@pytest.fixture
def as_member(api_client: AsyncClient, principal: Principal) -> Principal:
    """Make the caller of `api_client` a user without the admin role; return it."""
    member = replace(principal, roles=frozenset({UserRole.USER}))
    app.dependency_overrides[get_current_principal] = lambda: member
    return member
