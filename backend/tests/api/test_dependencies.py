"""Tests for the FastAPI dependency providers (the composition of the request graph)."""

import uuid
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from minio import Minio

from src.api import dependencies as deps
from src.domain.auth.entities import Principal
from src.domain.auth.service import AuthService
from src.domain.chunks.service import ChunkService
from src.domain.documents.service import DocumentService
from src.domain.tenants.service import TenantService
from src.domain.users.service import UserService
from src.infrastructure.database.postgres.repositories.chunk import (
    PostgresChunkRepository,
)
from src.infrastructure.database.postgres.repositories.document import (
    PostgresDocumentRepository,
)
from src.infrastructure.database.postgres.repositories.tenant import (
    PostgresTenantRepository,
)
from src.infrastructure.database.postgres.repositories.user import (
    PostgresUserRepository,
)
from src.infrastructure.security.tokens import create_access_token
from src.infrastructure.storage.minio.storage import MinioStorage
from src.libs.core.config import Settings
from src.libs.enums.user import UserRole
from src.libs.exceptions.exceptions import (
    AuthenticationException,
    PermissionDeniedException,
)


class TestCurrentCaller:
    """The caller comes from the bearer token; its tenant scopes every request."""

    @pytest.fixture
    def principal(self) -> Principal:
        return Principal(uuid.uuid4(), uuid.uuid4(), frozenset({UserRole.USER}))

    async def test_missing_token_is_rejected(self, test_settings: Settings):
        """
        GIVEN a request without a bearer token
        WHEN the caller is resolved
        THEN AuthenticationException is raised AND no user is looked up
        """
        auth_service = AsyncMock(spec=AuthService)

        with pytest.raises(AuthenticationException):
            await deps.get_current_principal(None, test_settings, auth_service)

        auth_service.resolve.assert_not_awaited()

    async def test_token_is_verified_and_its_user_resolved(
        self, test_settings: Settings, principal: Principal
    ):
        """
        GIVEN a valid token
        WHEN the caller is resolved
        THEN the user of the token's ids is the caller
        """
        auth_service = AsyncMock(spec=AuthService)
        auth_service.resolve.return_value = principal
        token = create_access_token(principal, test_settings)

        caller = await deps.get_current_principal(token, test_settings, auth_service)

        assert caller is principal
        auth_service.resolve.assert_awaited_once_with(
            principal.user_id, principal.tenant_id
        )

    async def test_current_tenant_is_the_callers_tenant(self, principal: Principal):
        """
        GIVEN a caller
        WHEN the current tenant is resolved
        THEN it is the caller's tenant
        """
        assert await deps.get_current_tenant_id(principal) == principal.tenant_id

    def test_require_admin(self, principal: Principal):
        """
        GIVEN a caller with and without the admin role
        WHEN the admin role is required
        THEN the admin passes AND the other caller gets PermissionDeniedException
        """
        admin = replace(principal, roles=frozenset({UserRole.ADMIN}))

        assert deps.require_admin(admin) is admin
        with pytest.raises(PermissionDeniedException):
            deps.require_admin(principal)


class TestProviders:
    """Each provider builds its object from the objects it depends on."""

    def test_storage_providers(self, test_settings: Settings):
        """
        GIVEN the MinIO client that the app created at startup
        WHEN the MinIO client and the storage adapter are provided
        THEN the provided client is that client AND the adapter wraps it
        """
        client = MagicMock(spec=Minio)
        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(storage_client=client))
        )

        provided = deps.get_minio_client(request)  # type: ignore[arg-type]
        storage = deps.get_minio_provider(test_settings, provided)

        assert provided is client  # the one client of the process, not a new one
        assert isinstance(storage, MinioStorage)
        assert storage.client is client

    def test_repositories_share_the_request_session(self):
        """
        GIVEN one request session
        WHEN the repositories are provided
        THEN every repository uses that session
        """
        session = MagicMock()

        repositories = [
            deps.get_tenant_repository(session),
            deps.get_user_repository(session),
            deps.get_document_repository(session),
            deps.get_chunk_repository(session),
        ]

        assert [type(r) for r in repositories] == [
            PostgresTenantRepository,
            PostgresUserRepository,
            PostgresDocumentRepository,
            PostgresChunkRepository,
        ]
        assert all(r._session is session for r in repositories)

    def test_login_limiter_is_one_per_process_with_the_configured_limit(self):
        """
        GIVEN the configured login attempts per minute
        WHEN the login limiter is provided twice
        THEN both calls return the same limiter with that limit
        """
        deps.get_login_rate_limiter.cache_clear()

        limiter = deps.get_login_rate_limiter()

        assert limiter is deps.get_login_rate_limiter()
        assert limiter.limit == deps.get_settings().login_attempts_per_minute

    def test_services_receive_their_dependencies(self):
        """
        GIVEN repositories and a storage adapter
        WHEN the services are provided
        THEN each service holds the given dependencies
        """
        repo, storage = MagicMock(), MagicMock()

        document_service = deps.get_document_service(repo, storage)
        tenant_service = deps.get_tenant_service(repo)
        hasher = deps.get_password_hasher()
        user_service = deps.get_user_service(repo, hasher)
        auth_service = deps.get_auth_service(repo, hasher)
        chunk_service = deps.get_chunk_service(repo, repo)

        assert isinstance(document_service, DocumentService)
        assert document_service.storage is storage
        assert isinstance(tenant_service, TenantService)
        assert isinstance(user_service, UserService)
        assert user_service.user_repository is repo
        assert user_service.hasher is hasher
        assert isinstance(auth_service, AuthService)
        assert auth_service.hasher is hasher
        assert deps.get_password_hasher() is hasher  # one hasher per process
        assert isinstance(chunk_service, ChunkService)
        assert chunk_service.chunk_repository is repo
