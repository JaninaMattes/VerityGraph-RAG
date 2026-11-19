"""Tests for the /documents endpoints."""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from httpx import AsyncClient

from src.domain.chunks.entities import (
    BoundingBox,
    ChunkDraft,
    ChunkingConfig,
    ChunkSpan,
    build_chunks,
)
from src.domain.documents.dataclasses import PresignedUrl
from src.libs.exceptions.exceptions import DocumentNotFoundException

pytestmark = pytest.mark.asyncio


class TestCreateUploadUrl:
    """POST /documents returns a presigned upload URL."""

    async def test_returns_201_and_presigned_url(
        self,
        doc_client: AsyncClient,
        mock_document_service: AsyncMock,
        mock_tenant_id,
        mock_document_id,
        mock_document_name,
    ):
        """
        GIVEN a valid filename and namespace
        WHEN POST /api/v1/documents is called
        THEN the response is 201 with the presigned URL from the service
        """
        mock_document_service.create_upload_url.return_value = PresignedUrl(
            document_id=mock_document_id,
            url="https://minio.local/bucket/contract.pdf?signature=abc",
            expires_at=timedelta(minutes=15),
            required_headers={"x-amz-meta-filename": mock_document_name},
        )

        response = await doc_client.post(
            "/api/v1/documents",
            json={"filename": mock_document_name, "namespace": "files"},
        )

        assert response.status_code == status.HTTP_201_CREATED
        body = response.json()
        assert body["document_id"] == str(mock_document_id)
        assert body["url"].endswith("signature=abc")
        assert body["required_headers"] == {"x-amz-meta-filename": mock_document_name}
        mock_document_service.create_upload_url.assert_awaited_once_with(
            tenant_id=mock_tenant_id, filename=mock_document_name, namespace="files"
        )

    @pytest.mark.parametrize(
        "payload",
        [
            {"filename": "", "namespace": "legal"},
            {"filename": "   ", "namespace": "legal"},
            {"filename": "a.pdf", "namespace": ""},
            {"namespace": "legal"},
        ],
        ids=["empty-filename", "blank-filename", "empty-namespace", "missing-filename"],
    )
    async def test_invalid_body_returns_422(
        self, doc_client: AsyncClient, mock_document_service: AsyncMock, payload
    ):
        """
        GIVEN a body with a missing, empty or blank required field
        WHEN POST /api/v1/documents is called
        THEN the response is 422 AND the service is not called
        """
        response = await doc_client.post("/api/v1/documents", json=payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        mock_document_service.create_upload_url.assert_not_awaited()


class TestGetDownloadUrl:
    """GET /documents/{document_id} returns a presigned download URL."""

    async def test_returns_200_and_presigned_url(
        self,
        doc_client: AsyncClient,
        mock_document_service,
        mock_document_id,
        mock_tenant_id,
    ):
        """
        GIVEN an existing document of the current tenant
        WHEN GET /api/v1/documents/{id} is called
        THEN the response is 200 with the presigned URL
        """
        mock_document_service.get_download_url.return_value = PresignedUrl(
            document_id=mock_document_id,
            url="https://minio.local/bucket/download?signature=xyz",
            expires_at=timedelta(minutes=5),
            required_headers={},
        )

        response = await doc_client.get(f"/api/v1/documents/{mock_document_id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["url"].endswith("signature=xyz")
        mock_document_service.get_download_url.assert_awaited_once_with(
            mock_document_id, mock_tenant_id
        )

    async def test_unknown_document_returns_404(
        self, doc_client: AsyncClient, mock_document_service, mock_document_id
    ):
        """
        GIVEN the service reports that the document does not exist
        WHEN GET /api/v1/documents/{id} is called
        THEN the response is 404
        """
        mock_document_service.get_download_url.side_effect = DocumentNotFoundException(
            mock_document_id
        )

        response = await doc_client.get(f"/api/v1/documents/{mock_document_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_invalid_id_returns_422(self, doc_client: AsyncClient):
        """
        GIVEN a path id that is not a UUID
        WHEN GET /api/v1/documents/{id} is called
        THEN the response is 422
        """
        response = await doc_client.get("/api/v1/documents/not-a-uuid")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestListChunks:
    """GET /documents/{document_id}/chunks returns the chunks with their evidence."""

    async def test_returns_chunks_with_spans(
        self,
        doc_client: AsyncClient,
        mock_chunk_service,
        mock_document_id,
        mock_tenant_id,
    ):
        """
        GIVEN a processed document with one chunk on page 1
        WHEN GET /api/v1/documents/{id}/chunks is called
        THEN the response is 200 with the chunk text, pages and highlight boxes
        """
        span = ChunkSpan(
            source_ref="#/texts/0",
            label="text",
            page_no=1,
            bbox=BoundingBox(72, 728.5, 180, 717.5),
            char_start=0,
            char_end=23,
        )
        mock_chunk_service.list_for_document.return_value = build_chunks(
            [
                ChunkDraft(
                    content="Acme invests in Globex.", token_count=5, spans=(span,)
                )
            ],
            document_id=mock_document_id,
            tenant_id=mock_tenant_id,
            config=ChunkingConfig(component="docling", component_version="1"),
        )

        response = await doc_client.get(f"/api/v1/documents/{mock_document_id}/chunks")

        assert response.status_code == status.HTTP_200_OK
        (chunk,) = response.json()
        assert chunk["content"] == "Acme invests in Globex."
        assert (chunk["chunk_index"], chunk["page_start"], chunk["page_end"]) == (
            0,
            1,
            1,
        )
        assert chunk["spans"][0]["bbox"] == {
            "left": 72.0,
            "top": 728.5,
            "right": 180.0,
            "bottom": 717.5,
            "origin": "BOTTOMLEFT",
        }
        assert "tenant_id" not in chunk
        mock_chunk_service.list_for_document.assert_awaited_once_with(
            mock_document_id, mock_tenant_id
        )

    async def test_unknown_document_returns_404(
        self, doc_client: AsyncClient, mock_chunk_service, mock_document_id
    ):
        """
        GIVEN the tenant has no such document
        WHEN GET /api/v1/documents/{id}/chunks is called
        THEN the response is 404
        """
        mock_chunk_service.list_for_document.side_effect = DocumentNotFoundException(
            mock_document_id
        )

        response = await doc_client.get(f"/api/v1/documents/{mock_document_id}/chunks")

        assert response.status_code == status.HTTP_404_NOT_FOUND
