"""Tests for the document value objects StorageKey and DocumentChecksum."""

import re
import uuid
from hashlib import sha256

import pytest
from src.domain.documents.dataclasses import DocumentChecksum, StorageKey

DOCUMENT_ID = uuid.UUID("39b02a26-86d0-4dd6-ae6e-7a0ea578f290")
TENANT_ID = uuid.UUID("12bf3456-7d89-12d3-a456-78c91cf2b34f")


def build_key(namespace: str = "files", filename: str | None = "report.pdf") -> str:
    return StorageKey.document(
        document_id=DOCUMENT_ID,
        tenant_id=TENANT_ID,
        namespace=namespace,
        original_filename=filename,
    ).value


class TestStorageKeyDocument:
    """StorageKey.document builds '<tenant>/<namespace>/<yyyy>/<mm>/<document_id>[.ext]'."""

    def test_key_has_tenant_namespace_date_and_id(self):
        """
        GIVEN a tenant, a namespace and a PDF filename
        WHEN a document key is built
        THEN the key has the documented layout with a zero-padded month
        """
        key = build_key()

        pattern = rf"{TENANT_ID}/files/\d{{4}}/\d{{2}}/{DOCUMENT_ID}\.pdf"
        assert re.fullmatch(pattern, key)

    @pytest.mark.parametrize(
        ("namespace", "expected"),
        [
            ("Legal-Docs", "legal-docs"),
            ("a b/c", "abc"),
            ("$$$", "files"),
            ("", "files"),
        ],
        ids=["lowercased", "unsafe-chars-removed", "only-unsafe-chars", "empty"],
    )
    def test_namespace_is_sanitised(self, namespace: str, expected: str):
        """
        GIVEN a namespace with upper case or unsafe characters
        WHEN a document key is built
        THEN the namespace is lowercased, cleaned, and falls back to 'files' if empty
        """
        assert build_key(namespace=namespace).split("/")[1] == expected

    @pytest.mark.parametrize(
        ("filename", "suffix"),
        [
            ("report.PDF", ".pdf"),
            ("archive.tar.gz", ".gz"),
            ("weird.p$d f", ".pdf"),
            ("no_extension", ""),
            ("trailing.", ""),
            ("bad.$$$", ""),
            (None, ""),
        ],
        ids=[
            "upper",
            "multi-dot",
            "unsafe",
            "none",
            "trailing-dot",
            "only-unsafe",
            "no-name",
        ],
    )
    def test_extension_is_sanitised(self, filename: str | None, suffix: str):
        """
        GIVEN a filename with or without a usable extension
        WHEN a document key is built
        THEN only a cleaned, lowercased last extension is appended
        """
        assert build_key(filename=filename).endswith(f"{DOCUMENT_ID}{suffix}")


class TestStorageKeyDocumentId:
    """StorageKey.document_id reads the document id back from a key."""

    @pytest.mark.parametrize(
        "filename", ["report.pdf", None], ids=["with-ext", "without-ext"]
    )
    def test_document_id_round_trips(self, filename: str | None):
        """
        GIVEN a key built by StorageKey.document
        WHEN the document id is read from the key
        THEN it equals the original document id
        """
        key = StorageKey(build_key(filename=filename))

        assert key.document_id == DOCUMENT_ID

    def test_invalid_last_segment_raises_value_error(self):
        """
        GIVEN a key whose last segment is not a UUID
        WHEN the document id is read
        THEN a ValueError is raised
        """
        with pytest.raises(ValueError):
            _ = StorageKey("tenant/files/2026/01/not-a-uuid.pdf").document_id


class TestStorageKeyTenantId:
    """StorageKey.tenant_id reads the tenant from the first key segment."""

    def test_tenant_id_round_trips(self):
        """
        GIVEN a key built by StorageKey.document
        WHEN the tenant id is read from the key
        THEN it equals the original tenant id
        """
        assert StorageKey(build_key()).tenant_id == TENANT_ID

    @pytest.mark.parametrize(
        "key", ["not-a-uuid/files/2026/01/x.pdf", ""], ids=["not-uuid", "empty"]
    )
    def test_invalid_first_segment_raises_value_error(self, key: str):
        """
        GIVEN a key whose first segment is not a UUID
        WHEN the tenant id is read
        THEN a ValueError is raised
        """
        with pytest.raises(ValueError):
            _ = StorageKey(key).tenant_id


class TestDocumentChecksum:
    """DocumentChecksum normalises and computes SHA-256 checksums."""

    def test_from_hex_lowercases(self):
        """
        GIVEN an upper-case hex digest
        WHEN a checksum is created from it
        THEN the value is lower-case
        """
        assert DocumentChecksum.from_hex("ABCDEF").value == "abcdef"

    def test_from_bytes_is_sha256_and_str_is_value(self):
        """
        GIVEN some bytes
        WHEN a checksum is created from them
        THEN the value is their SHA-256 hex digest AND str() returns the value
        """
        checksum = DocumentChecksum.from_bytes(b"hello")

        assert checksum.value == sha256(b"hello").hexdigest()
        assert str(checksum) == checksum.value
