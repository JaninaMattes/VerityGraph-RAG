from datetime import timedelta

from httpx import AsyncClient
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
    Test suite for the Documents API endpoints.
    Ensures the application correctly generates presigned Upload/Download URLs.
    """

    # ---------------------------------------------------------
    # POST /documents (Create Upload URL)
    # ---------------------------------------------------------

    async def test_create_upload_url_returns_201_and_presigned_url(
        self,
        doc_client,
        mock_document_service,
        mock_tenant_id,
        mock_document_id,
        mock_document_name,
    ):
        """
        GIVEN the application is running in the testing environment and filename, namespace and mime_type are known
        WHEN a HTTP POST request is made against '/api/v1/documents'
        THEN a HTTP status code of 201 as well as the pre-signed uploade URL are returned
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

        payload = {"filename": "contract.pdf", "namespace": "files"}

        # 2. Act
        response = await doc_client.post("/api/v1/documents", json=payload)

        # 3. Assert
        # Assert HTTP Response
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == mock_service_response.model_dump(mode="json")

        # Assert Service Interaction
        mock_document_service.create_upload_url.assert_awaited_once_with(
            tenant_id=mock_tenant_id, filename="contract.pdf", namespace="files"
        )

    async def test_create_new_document_and_handle_empty_parameter_returns_400(
        self, doc_client: AsyncClient
    ):
        """
        GIVEN the application is running in the testing environment
        WHEN a HTTP POST request is made against '/api/v1/documents' with the request parameter 'filename' is empty
        THEN a HTTP status code of 400 with the message that the parameter is missing is returned
        """

        # 1. Arrange
        payload = {"filename": "", "namespace": "legal"}

        # 2. Act
        response = await doc_client.post("/api/v1/documents", json=payload)

        # 3. Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {"detail": "Missing required parameter 'filename'"}

    async def test_create_upload_url_and_handle_missing_doc_returns_422(
        self, doc_client: AsyncClient
    ):
        """
        GIVEN the application is running in the testing environment and filename, namespace and mime_type are known
        WHEN a POST request is made against '/api/v1/documents' with a namespace parameter that does not exist
        THEN a HTTP status code of 422 is returned
        """
        # 1. Arrange
        payload = {"namespace": "legal"}

        # 2. Act
        response = await doc_client.post("/api/v1/documents", json=payload)

        # 3. Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        error_details = response.json()["detail"]
        assert any(err["loc"] == ["body", "filename"] for err in error_details)

    # ---------------------------------------------------------
    # GET /documents/{document_id} (Download URL)
    # ---------------------------------------------------------

    async def test_get_download_url_returns_presigned_url_and_200(
        self,
        doc_client: AsyncClient,
        mock_document_service,
        mock_document_id,
        mock_tenant_id,
    ):
        """
        GIVEN the application is running in the testing environment and the correct document id are known
        WHEN a GET request is made against '/api/v1/documents' with a document id as parameter
        THEN a HTTP status code of 200 as well as the pre-signed download URL are returned
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
        response = await doc_client.get(f"/api/v1/documents/{mock_document_id}")

        # 3. Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == mock_response.model_dump(mode="json")
        mock_document_service.get_download_url.assert_awaited_once_with(
            mock_document_id, mock_tenant_id
        )

    async def test_get_download_url_and_handle_not_found_returns_404(
        self, doc_client: AsyncClient, mock_document_service, mock_document_id
    ):
        """
        GIVEN The test domain for a specific document id is not found.
        WHEN a GET request is made against '/api/v1/documents' with a document id as parameter
        THEN The service raises a Domain Exception (DocumentNotFoundException), which the FastAPI global exception handler correctly translates it to an HTTP 404.
        """
        # 1. Arrange: Simulate the service failing
        mock_document_service.get_download_url.side_effect = DocumentNotFoundException(
            mock_document_id
        )

        # 2. Act
        response = await doc_client.get(f"/api/v1/documents/{mock_document_id}")

        # 3. Assert: Ensure the API returns 404
        assert response.status_code == status.HTTP_404_NOT_FOUND
