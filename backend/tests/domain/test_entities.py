"""Tests for the domain entities: state transitions, identity and representation."""

import copy
import uuid

import pytest

from src.domain.documents.dataclasses import StorageKey, StoredFile
from src.libs.enums.document import DocumentStatus, LanguageType
from src.libs.enums.ingestionjob import ProcessingStatus
from src.libs.enums.tenant import TenantStatus
from src.libs.enums.user import UserStatus


class TestDocumentEntity:
    """DocumentEntity status changes and storage metadata."""

    @pytest.mark.parametrize(
        ("method", "expected"),
        [
            ("mark_uploaded", DocumentStatus.UPLOADED),
            ("mark_processed", DocumentStatus.PROCESSED),
            ("mark_failed", DocumentStatus.FAILED),
        ],
    )
    def test_status_transition_updates_timestamp(
        self, document_entity, method, expected
    ):
        """
        GIVEN a document
        WHEN a status transition method is called
        THEN the status changes AND updated_at moves forward
        """
        before = document_entity.updated_at

        getattr(document_entity, method)()

        assert document_entity.status is expected
        assert document_entity.updated_at > before

    def test_mark_ready_sets_language(self, document_entity):
        """
        GIVEN a processed document
        WHEN it is marked ready with a language
        THEN the status is READY AND the language is stored
        """
        document_entity.mark_ready(language=LanguageType.ENGLISH)

        assert document_entity.status is DocumentStatus.READY
        assert document_entity.language is LanguageType.ENGLISH

    def test_mark_deleted_records_who_and_when(self, document_entity):
        """
        GIVEN a document
        WHEN a user deletes it
        THEN the status is DELETED AND deleted_by and deleted_at are set
        """
        user_id = uuid.uuid4()

        document_entity.mark_deleted(user_id)

        assert document_entity.status is DocumentStatus.DELETED
        assert document_entity.deleted_by == user_id
        assert document_entity.deleted_at is not None

    def test_update_storage_metadata_copies_all_fields(self, document_entity):
        """
        GIVEN stored-file metadata from the storage provider
        WHEN the document is updated with it
        THEN all storage fields equal the metadata
        """
        stored = StoredFile(
            storage_key=StorageKey("new/key"),
            mime_type="text/csv",
            size_bytes=10,
            bucket_name="b",
            version_id="v1",
            etag="e",
        )

        document_entity.update_storage_metadata(stored)

        assert document_entity.storage_key == stored.storage_key
        assert (document_entity.mime_type, document_entity.size_bytes) == (
            "text/csv",
            10,
        )
        assert (document_entity.bucket_name, document_entity.version_id) == ("b", "v1")
        assert document_entity.etag == "e"

    def test_identity_and_repr(self, document_entity):
        """
        GIVEN a document
        WHEN it is compared, hashed and printed
        THEN identity uses document_id only AND repr is a closed expression
        """
        assert document_entity == copy.copy(document_entity)
        assert document_entity != "other"
        assert hash(document_entity) == hash(document_entity.document_id)
        assert repr(document_entity).startswith("DocumentEntity(")
        assert repr(document_entity).endswith(")")


class TestIngestionJobEntity:
    """IngestionJobEntity terminal states."""

    def test_mark_completed_clears_stage(self, job_entity):
        """
        GIVEN a running job
        WHEN it is completed
        THEN the status is COMPLETED, the stage is None and finished_at is set
        """
        job_entity.mark_completed()

        assert job_entity.status is ProcessingStatus.COMPLETED
        assert job_entity.current_stage is None
        assert job_entity.finished_at is not None

    def test_mark_failed_records_error(self, job_entity):
        """
        GIVEN a running job
        WHEN it fails with an error message
        THEN the status is FAILED AND the message is stored
        """
        job_entity.mark_failed("boom")

        assert job_entity.status is ProcessingStatus.FAILED
        assert job_entity.error_message == "boom"
        assert job_entity.finished_at is not None

    @pytest.mark.parametrize("reason", ["user request", None])
    def test_mark_cancelled_with_optional_reason(self, job_entity, reason):
        """
        GIVEN a running job
        WHEN it is cancelled with or without a reason
        THEN the status is CANCELLED AND the reason is stored
        """
        job_entity.mark_cancelled(reason)

        assert job_entity.status is ProcessingStatus.CANCELLED
        assert job_entity.error_message == reason

    def test_identity_uses_job_id(self, job_entity):
        """
        GIVEN a job
        WHEN it is compared and hashed
        THEN identity uses job_id only, like the other entities
        """
        assert job_entity == copy.copy(job_entity)
        assert job_entity != "other"
        assert hash(job_entity) == hash(job_entity.job_id)


class TestTenantEntity:
    """TenantEntity lifecycle and identity."""

    def test_lifecycle(self, tenant_entity):
        """
        GIVEN a new tenant
        WHEN it is activated, updated and then deleted
        THEN the status is ACTIVE and then SUSPENDED with the deleting user recorded
        """
        user_id = uuid.uuid4()
        tenant_entity.mark_activated()
        assert tenant_entity.status is TenantStatus.ACTIVE

        before = tenant_entity.updated_at
        tenant_entity.mark_updated()
        assert tenant_entity.updated_at > before

        tenant_entity.mark_deleted(user_id)
        assert tenant_entity.status is TenantStatus.SUSPENDED
        assert tenant_entity.deleted_by == user_id

    def test_identity_and_repr(self, tenant_entity):
        """
        GIVEN a tenant
        WHEN it is compared, hashed and printed
        THEN identity uses tenant_id only AND repr names the organisation
        """
        assert tenant_entity == copy.copy(tenant_entity)
        assert tenant_entity != object()
        assert hash(tenant_entity) == hash(tenant_entity.tenant_id)
        assert tenant_entity.organisation in repr(tenant_entity)


class TestUserEntity:
    """UserEntity lifecycle and identity."""

    def test_lifecycle(self, user_entity):
        """
        GIVEN a new user
        WHEN the user is activated, updated and then deleted
        THEN the status is ACTIVE and then DISABLED
        """
        user_entity.mark_activated()
        assert user_entity.status is UserStatus.ACTIVE

        before = user_entity.updated_at
        user_entity.mark_updated()
        assert user_entity.updated_at > before

        user_entity.mark_deleted(user_entity.tenant_id)
        assert user_entity.status is UserStatus.DISABLED
        assert user_entity.deleted_at is not None

    def test_identity_and_repr(self, user_entity):
        """
        GIVEN a user
        WHEN the user is compared, hashed and printed
        THEN identity uses user_id only AND repr names the username
        """
        assert user_entity == copy.copy(user_entity)
        assert user_entity != object()
        assert hash(user_entity) == hash(user_entity.user_id)
        assert user_entity.username in repr(user_entity)
