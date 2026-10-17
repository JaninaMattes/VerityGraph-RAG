from datetime import timedelta

import pytest
from fastapi import status
from src.libs.exceptions.exceptions import DocumentNotFoundException
from src.libs.schemas.document import PresignedURLResponse

pytestmark = pytest.mark.asyncio

# ==========================================================
# Endpoint 1: /documents
# ==========================================================


class TestDocumentAPIEndpoints:
    """
    Test suite for the Health and Documents API endpoints.
    Ensures the application correctly generates presigned Upload/Download URLs.
    """

    # ---------------------------------------------------------
    # POST /documents (Create Upload URL)
    # ---------------------------------------------------------

    async def test_create_upload_url_returns_201_and_presigned_url(
        self,
        client,
        mock_document_service,
        mock_tenant_id,
        mock_document_id,
        mock_document_name,
    ):
        """
        GIVEN
        WHEN
        THEN
        """
        # 1. Arrange
        mock_service_response = PresignedURLResponse(
            document_id=mock_document_id,
            url="https://minio.local/bucket/contract.pdf?signature=abc",
            expires_at=timedelta(minutes=15),
            required_headers={
                "x-amz-meta-tenant-id": str(mock_tenant_id),
                "x-amz-meta-filename": mock_document_name,
                "x-amz-meta-document-type": "PDF",
            },
        )
        mock_document_service.create_upload_url.return_value = mock_service_response

        payload = {"filename": "contract.pdf", "namespace": "legal"}

        # 2. Act
        response = await client.post("/api/v1/documents", json=payload)

        # 3. Assert HTTP Response
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == mock_service_response.model_dump(mode="json")

        # 4. Assert Service Interaction
        mock_document_service.create_upload_url.assert_awaited_once_with(
            tenant_id=mock_tenant_id, filename="contract.pdf", namespace="legal"
        )

    async def test_create_upload_url_and_handle_missing_doc_returns_422(self, client):
        """
        GIVEN
        WHEN
        THEN
        """
        # Act
        response = await client.post("/api/v1/documents", json={"namespace": "legal"})

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        error_details = response.json()["detail"]
        assert any(err["loc"] == ["body", "filename"] for err in error_details)

    # ---------------------------------------------------------
    # GET /documents/{document_id} (Download URL)
    # ---------------------------------------------------------

    async def test_get_download_url_returns_presigned_url_and_200(
        self, client, mock_document_service, mock_document_id, mock_tenant_id
    ):
        """
        GIVEN
        WHEN
        THEN
        """
        # 1. Arrange
        mock_response = PresignedURLResponse(
            document_id=mock_document_id,
            url="https://minio.local/bucket/download?signature=xyz",
            expires_at=timedelta(minutes=15),
            required_headers={},
        )
        mock_document_service.get_download_url.return_value = mock_response

        # 2. Act
        response = await client.get(f"/api/v1/documents/{mock_document_id}")

        # 3. Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == mock_response.model_dump(mode="json")
        mock_document_service.get_download_url.assert_awaited_once_with(
            mock_document_id, mock_tenant_id
        )

    async def test_get_download_url_and_handle_not_found_returns_404(
        self, client, mock_document_service, mock_document_id
    ):
        """
        GIVEN The test domain is not found.
        WHEN
        THEN The service raises a Domain Exception (DocumentNotFoundException), which the FastAPI global exception handler correctly translates it to an HTTP 404.
        """
        # 1. Arrange: Simulate the service failing
        mock_document_service.get_download_url.side_effect = DocumentNotFoundException(
            mock_document_id
        )

        # 2. Act
        response = await client.get(f"/api/v1/documents/{mock_document_id}")

        # 3. Assert: Ensure the API returns 404
        assert response.status_code == status.HTTP_404_NOT_FOUND
