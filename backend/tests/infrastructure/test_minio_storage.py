"""Tests for the MinIO storage adapter and its factories."""

from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from minio import Minio, S3Error

from src.domain.documents.dataclasses import StorageKey, StoredFile
from src.infrastructure.storage.client import create_storage_client
from src.infrastructure.storage.minio.storage import MinioStorage
from src.infrastructure.storage.service import create_storage_service
from src.libs.core.config import Settings
from src.libs.exceptions.exceptions import (
    BucketNotFoundException,
    ObjectNotFoundException,
    StorageAccessDeniedException,
    StorageException,
)

KEY = StorageKey("tenant/files/2026/01/doc.pdf")


def s3_error(code: str) -> S3Error:
    return S3Error(MagicMock(), code, "message", "resource", "request", "host")


@pytest.fixture
def client() -> MagicMock:
    return MagicMock(spec=Minio)


@pytest.fixture
def storage(client: MagicMock) -> MinioStorage:
    return MinioStorage(client=client, bucket_name="files")


class TestCreateBucket:
    """create_bucket creates the bucket only when it is missing."""

    @pytest.mark.parametrize(("exists", "creates"), [(True, False), (False, True)])
    def test_bucket_is_created_only_if_missing(self, storage, client, exists, creates):
        """
        GIVEN the bucket exists or not
        WHEN create_bucket is called
        THEN make_bucket is called only for a missing bucket
        """
        client.bucket_exists.return_value = exists

        storage.create_bucket()

        assert client.make_bucket.called is creates


class TestCheckAvailable:
    """check_available succeeds only when the bucket can be reached."""

    def test_existing_bucket_passes(self, storage, client):
        """
        GIVEN the bucket exists
        WHEN check_available is called
        THEN no error is raised
        """
        client.bucket_exists.return_value = True

        storage.check_available()

        client.bucket_exists.assert_called_once_with(bucket_name="files")

    def test_missing_bucket_raises(self, storage, client):
        """
        GIVEN the bucket does not exist
        WHEN check_available is called
        THEN BucketNotFoundException is raised
        """
        client.bucket_exists.return_value = False

        with pytest.raises(BucketNotFoundException):
            storage.check_available()

    def test_s3_error_is_translated(self, storage, client):
        """
        GIVEN MinIO denies access
        WHEN check_available is called
        THEN the S3 error becomes StorageAccessDeniedException
        """
        client.bucket_exists.side_effect = s3_error("AccessDenied")

        with pytest.raises(StorageAccessDeniedException):
            storage.check_available()


class TestCreatePresignedUrl:
    """create_presigned_url signs metadata into PUT URLs only."""

    def test_put_signs_prefixed_metadata(self, storage, client):
        """
        GIVEN metadata keys with and without the 'x-amz-meta-' prefix
        WHEN a PUT URL is created
        THEN every key is signed once, lower-case and with the prefix
        """
        client.get_presigned_url.return_value = "https://signed"

        url = storage.create_presigned_url(
            KEY,
            timedelta(minutes=1),
            "put",
            {"Tenant_ID": "t", "x-amz-meta-filename": "f"},
        )

        assert url == "https://signed"
        kwargs = client.get_presigned_url.call_args.kwargs
        assert kwargs["object_name"] == KEY.value
        assert kwargs["extra_query_params"] == {
            "x-amz-meta-tenant_id": "t",
            "x-amz-meta-filename": "f",
        }

    def test_get_ignores_metadata(self, storage, client):
        """
        GIVEN metadata
        WHEN a GET URL is created
        THEN no metadata is signed into the URL
        """
        storage.create_presigned_url(KEY, timedelta(minutes=1), "GET", {"a": "b"})

        assert client.get_presigned_url.call_args.kwargs["extra_query_params"] is None


class TestObjectOperations:
    """Metadata, delete and download pass the right values to the client."""

    @pytest.mark.parametrize(("size", "expected"), [(42, 42), (None, -1)])
    def test_metadata_is_mapped_to_stored_file(self, storage, client, size, expected):
        """
        GIVEN an object with a known or unknown size
        WHEN its metadata is read
        THEN a StoredFile is returned AND an unknown size is -1
        """
        client.stat_object.return_value = SimpleNamespace(
            content_type="application/pdf",
            size=size,
            bucket_name="files",
            version_id="v",
            etag="e",
        )

        assert storage.get_obj_metadata(KEY) == StoredFile(
            storage_key=KEY,
            mime_type="application/pdf",
            size_bytes=expected,
            bucket_name="files",
            version_id="v",
            etag="e",
        )

    def test_delete_removes_object(self, storage, client):
        """
        GIVEN a stored object
        WHEN it is deleted
        THEN the client removes the object from the bucket
        """
        storage.delete_object(KEY)

        client.remove_object.assert_called_once_with(
            bucket_name="files", object_name=KEY.value
        )

    def test_download_writes_to_path(self, storage, client):
        """
        GIVEN a stored object
        WHEN it is downloaded
        THEN the client writes it to the given local path
        """
        storage.download_object("files", KEY.value, "/tmp/x.pdf")

        client.fget_object.assert_called_once_with(
            "files", KEY.value, file_path="/tmp/x.pdf"
        )


OPERATIONS: dict[str, tuple[str, Any]] = {
    "create_bucket": ("bucket_exists", lambda s: s.create_bucket()),
    "presign": (
        "get_presigned_url",
        lambda s: s.create_presigned_url(KEY, timedelta(minutes=1), "GET"),
    ),
    "metadata": ("stat_object", lambda s: s.get_obj_metadata(KEY)),
    "delete": ("remove_object", lambda s: s.delete_object(KEY)),
    "download": (
        "fget_object",
        lambda s: s.download_object("files", KEY.value, "/tmp/x"),
    ),
}
OBJECT_OPERATIONS = ["presign", "metadata", "delete", "download"]


class TestErrorTranslation:
    """Every operation maps S3 error codes to the same domain exceptions."""

    @pytest.mark.parametrize("operation", list(OPERATIONS))
    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            ("NoSuchBucket", BucketNotFoundException),
            ("AccessDenied", StorageAccessDeniedException),
            ("InvalidAccessKeyId", StorageAccessDeniedException),
            ("InternalError", StorageException),
        ],
    )
    def test_s3_error_codes_are_translated(
        self, storage, client, operation, code, expected
    ):
        """
        GIVEN the MinIO client fails with an S3 error code
        WHEN any storage operation runs
        THEN the matching domain exception is raised (never swallowed)
        """
        client_method, call = OPERATIONS[operation]
        getattr(client, client_method).side_effect = s3_error(code)

        with pytest.raises(expected):
            call(storage)

    @pytest.mark.parametrize("operation", OBJECT_OPERATIONS)
    def test_missing_object_raises_object_not_found(self, storage, client, operation):
        """
        GIVEN the object does not exist ('NoSuchKey')
        WHEN an object operation runs
        THEN ObjectNotFoundException is raised with the key
        """
        client_method, call = OPERATIONS[operation]
        getattr(client, client_method).side_effect = s3_error("NoSuchKey")

        with pytest.raises(ObjectNotFoundException, match="doc.pdf"):
            call(storage)


class TestFactories:
    """The factories build the client and the adapter from the settings."""

    def test_client_and_service_use_settings(self, test_settings: Settings):
        """
        GIVEN the application settings
        WHEN the storage client and the storage service are created
        THEN the service wraps the client and uses the default bucket
        """
        client = create_storage_client(test_settings)
        service = create_storage_service(client, test_settings)

        assert isinstance(client, Minio)
        assert service.client is client
        assert service.bucket_name == test_settings.minio_default_bucket
