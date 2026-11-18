"""Tests for the domain services (tenants, users, documents).

Services return domain objects and let domain and infrastructure errors propagate
unchanged; the API layer maps them to HTTP responses.
"""

import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from src.domain.documents.dataclasses import PresignedUrl
from src.domain.documents.service import DocumentService
from src.domain.tenants.dataclasses import Tenant, UpdateTenant
from src.domain.tenants.service import TenantService
from src.domain.users.dataclasses import UpdateUser, User
from src.domain.users.service import UserService
from src.libs.enums.tenant import TenantStatus
from src.libs.enums.user import UserRole, UserStatus
from src.libs.exceptions.exceptions import (
    BucketNotFoundException,
    DatabaseInternalException,
    DocumentNotFoundException,
    StorageOperationException,
)

pytestmark = pytest.mark.asyncio


class TestTenantService:
    """TenantService creates, reads, updates and deletes tenants."""

    @pytest.fixture
    def repo(self) -> AsyncMock:
        return AsyncMock()

    async def test_create_builds_new_tenant(self, repo):
        """
        GIVEN an organisation name
        WHEN a tenant is created
        THEN the repository receives a CREATED tenant with a new id
        AND the service returns the stored entity
        """
        repo.create.side_effect = lambda entity: entity

        tenant = await TenantService(repo).create(Tenant("ACME"))

        assert tenant.organisation == "ACME"
        assert tenant.status is TenantStatus.CREATED
        assert isinstance(tenant.tenant_id, uuid.UUID)

    async def test_get_returns_repository_entity(self, repo, tenant_entity):
        """
        GIVEN a stored tenant
        WHEN it is read by id
        THEN the service returns the stored entity
        """
        repo.get_one.return_value = tenant_entity

        assert await TenantService(repo).get(tenant_entity.tenant_id) is tenant_entity

    async def test_update_changes_organisation(self, repo, tenant_entity):
        """
        GIVEN a stored tenant
        WHEN its organisation is updated
        THEN the repository saves the entity with the new organisation
        """
        repo.get_one.return_value = tenant_entity
        repo.update.side_effect = lambda entity: entity

        updated = await TenantService(repo).update(
            UpdateTenant(tenant_entity.tenant_id, organisation="New Name")
        )

        assert updated.organisation == "New Name"
        repo.update.assert_awaited_once_with(tenant_entity)

    async def test_delete_delegates_to_repository(self, repo, mock_tenant_id):
        """
        GIVEN a tenant id
        WHEN the tenant is deleted
        THEN the repository deletes that id
        """
        await TenantService(repo).delete(mock_tenant_id)

        repo.delete.assert_awaited_once_with(mock_tenant_id)

    async def test_errors_propagate_unchanged(self, repo, mock_tenant_id):
        """
        GIVEN the repository fails
        WHEN a tenant is read
        THEN the original error propagates
        """
        repo.get_one.side_effect = DatabaseInternalException("db down")

        with pytest.raises(DatabaseInternalException):
            await TenantService(repo).get(mock_tenant_id)


class TestUserService:
    """UserService creates, reads, updates and deletes users within a tenant."""

    @pytest.fixture
    def repo(self) -> AsyncMock:
        return AsyncMock()

    async def test_create_builds_new_user(self, repo, mock_tenant_id):
        """
        GIVEN user details and a tenant
        WHEN a user is created
        THEN the repository receives a CREATED user with role USER in that tenant
        """
        repo.create.side_effect = lambda entity: entity

        user = await UserService(repo).create(
            User("ada", "ada@example.com", "hash"), mock_tenant_id
        )

        assert (user.username, user.email) == ("ada", "ada@example.com")
        assert user.tenant_id == mock_tenant_id
        assert user.roles == [UserRole.USER]
        assert user.status is UserStatus.CREATED

    async def test_get_reads_within_tenant(self, repo, user_entity):
        """
        GIVEN a stored user
        WHEN the user is read by id and tenant
        THEN the service returns the stored entity
        """
        repo.get_one.return_value = user_entity

        result = await UserService(repo).get(user_entity.user_id, user_entity.tenant_id)

        assert result is user_entity
        repo.get_one.assert_awaited_once_with(
            user_entity.user_id, user_entity.tenant_id
        )

    async def test_update_changes_name_and_email(self, repo, user_entity):
        """
        GIVEN a stored user
        WHEN the username and email are updated
        THEN the repository saves the entity with the new values
        """
        repo.get_one.return_value = user_entity
        repo.update.side_effect = lambda entity: entity

        updated = await UserService(repo).update(
            UpdateUser(
                user_entity.user_id, user_entity.tenant_id, "grace", "g@example.com"
            )
        )

        assert (updated.username, updated.email) == ("grace", "g@example.com")

    async def test_delete_delegates_to_repository(
        self, repo, mock_user_id, mock_tenant_id
    ):
        """
        GIVEN a user id and a tenant id
        WHEN the user is deleted
        THEN the repository deletes exactly that user
        """
        await UserService(repo).delete(mock_user_id, mock_tenant_id)

        repo.delete.assert_awaited_once_with(mock_user_id, mock_tenant_id)


class TestDocumentService:
    """DocumentService issues presigned upload and download URLs."""

    @pytest.fixture
    def storage(self) -> MagicMock:
        storage = MagicMock()
        storage.create_presigned_url.return_value = "https://minio/signed"
        return storage

    @pytest.fixture
    def repo(self) -> AsyncMock:
        return AsyncMock()

    async def test_upload_url_signs_put_with_metadata(
        self, storage, repo, mock_tenant_id
    ):
        """
        GIVEN a filename with an extension
        WHEN an upload URL is requested
        THEN the storage signs a 15-minute PUT URL with the tenant metadata
        AND the result lists the headers that the client must send
        """
        result = await DocumentService(storage, repo).create_upload_url(
            mock_tenant_id, "report.pdf", "legal"
        )

        assert isinstance(result, PresignedUrl)
        assert result.url == "https://minio/signed"
        assert result.expires_at == timedelta(minutes=15)
        kwargs = storage.create_presigned_url.call_args.kwargs
        assert kwargs["method"] == "PUT"
        assert kwargs["storage_key"].document_id == result.document_id
        assert kwargs["user_metadata"]["document_type"] == "PDF"
        assert result.required_headers["x-amz-meta-tenant-id"] == str(mock_tenant_id)

    async def test_upload_url_without_extension_is_unknown_type(
        self, storage, repo, mock_tenant_id
    ):
        """
        GIVEN a filename without an extension
        WHEN an upload URL is requested
        THEN the document type is 'UNKNOWN'
        """
        result = await DocumentService(storage, repo).create_upload_url(
            mock_tenant_id, "README"
        )

        assert result.required_headers["x-amz-meta-document-type"] == "UNKNOWN"

    async def test_missing_bucket_is_created_and_signing_retried(
        self, storage, repo, mock_tenant_id
    ):
        """
        GIVEN the bucket does not exist yet
        WHEN an upload URL is requested
        THEN the bucket is created AND signing is retried once
        """
        storage.create_presigned_url.side_effect = [
            BucketNotFoundException("files"),
            "https://minio/signed",
        ]

        result = await DocumentService(storage, repo).create_upload_url(
            mock_tenant_id, "a.pdf"
        )

        storage.create_bucket.assert_called_once_with()
        assert storage.create_presigned_url.call_count == 2
        assert result.url == "https://minio/signed"

    async def test_storage_error_propagates(self, storage, repo, mock_tenant_id):
        """
        GIVEN the storage fails with an operation error
        WHEN an upload URL is requested
        THEN the storage error propagates
        """
        storage.create_presigned_url.side_effect = StorageOperationException(
            "files", "x"
        )

        with pytest.raises(StorageOperationException):
            await DocumentService(storage, repo).create_upload_url(
                mock_tenant_id, "a.pdf"
            )

    async def test_download_url_signs_get_for_stored_key(
        self, storage, repo, document_entity
    ):
        """
        GIVEN a stored document
        WHEN a download URL is requested
        THEN the storage signs a 5-minute GET URL for the stored key
        """
        repo.get_one.return_value = document_entity

        result = await DocumentService(storage, repo).get_download_url(
            document_entity.document_id, document_entity.tenant_id
        )

        assert storage.create_presigned_url.call_args == call(
            storage_key=document_entity.storage_key,
            expires_at=timedelta(minutes=5),
            method="GET",
        )
        assert result.expires_at == timedelta(minutes=5)
        assert result.required_headers["x-amz-meta-document-type"] == "pdf"

    async def test_download_url_with_unknown_type(self, storage, repo, document_entity):
        """
        GIVEN a stored document without a document type
        WHEN a download URL is requested
        THEN the document type header is 'unknown'
        """
        document_entity.document_type = None
        repo.get_one.return_value = document_entity

        result = await DocumentService(storage, repo).get_download_url(
            document_entity.document_id, document_entity.tenant_id
        )

        assert result.required_headers["x-amz-meta-document-type"] == "unknown"

    async def test_download_of_missing_document_raises_not_found(
        self, storage, repo, mock_document_id, mock_tenant_id
    ):
        """
        GIVEN the document does not exist
        WHEN a download URL is requested
        THEN DocumentNotFoundException propagates AND nothing is signed
        """
        repo.get_one.side_effect = DocumentNotFoundException(mock_document_id)

        with pytest.raises(DocumentNotFoundException):
            await DocumentService(storage, repo).get_download_url(
                mock_document_id, mock_tenant_id
            )

        storage.create_presigned_url.assert_not_called()
