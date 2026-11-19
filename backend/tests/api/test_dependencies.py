"""Tests for the FastAPI dependency providers (the composition of the request graph)."""

import uuid
from unittest.mock import MagicMock

from minio import Minio

from src.api import dependencies as deps
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
from src.infrastructure.storage.minio.storage import MinioStorage
from src.libs.core.config import Settings


class TestCurrentTenant:
    """The current tenant is the configured development tenant."""

    async def test_returns_dev_tenant_id(self, test_settings: Settings):
        """
        GIVEN settings with DEV_TENANT_ID
        WHEN the current tenant is resolved
        THEN it is that id as a UUID
        """
        assert await deps.get_current_tenant_id(test_settings) == uuid.UUID(
            test_settings.dev_tenant_id
        )


class TestProviders:
    """Each provider builds its object from the objects it depends on."""

    def test_storage_providers(self, test_settings: Settings):
        """
        GIVEN the settings
        WHEN the MinIO client and the storage adapter are provided
        THEN the adapter wraps the client
        """
        client = deps.get_minio_client(test_settings)
        storage = deps.get_minio_provider(test_settings, client)

        assert isinstance(client, Minio)
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

    def test_services_receive_their_dependencies(self):
        """
        GIVEN repositories and a storage adapter
        WHEN the services are provided
        THEN each service holds the given dependencies
        """
        repo, storage = MagicMock(), MagicMock()

        document_service = deps.get_document_service(repo, storage)
        tenant_service = deps.get_tenant_service(repo)
        user_service = deps.get_user_service(repo)
        chunk_service = deps.get_chunk_service(repo, repo)

        assert isinstance(document_service, DocumentService)
        assert document_service.storage is storage
        assert isinstance(tenant_service, TenantService)
        assert isinstance(user_service, UserService)
        assert user_service.user_repository is repo
        assert isinstance(chunk_service, ChunkService)
        assert chunk_service.chunk_repository is repo
