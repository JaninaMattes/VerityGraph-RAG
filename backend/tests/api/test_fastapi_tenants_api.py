from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from fastapi import status
from httpx import AsyncClient

from src.domain.tenants.dataclasses import Tenant, UpdateTenant
from src.libs.enums.tenant import TenantStatus
from src.libs.exceptions.exceptions import (
    DatabaseInternalException,
    TenantNotFoundException,
)
from src.libs.schemas.tenant import TenantResponse

pytestmark = pytest.mark.asyncio

# ==========================================================
# Endpoint: /tenants
# ==========================================================


class TestTenantAPIEndpoints:
    """
    Test suite for the Tenants API endpoints.
    Ensures the application correctly generates presigned Upload/Download URLs.
    """

    # ---------------------------------------------------------
    # POST /tenants (Create new Tenant entry)
    # ---------------------------------------------------------

    async def test_create_new_tenant_entry_returns_status_and_201(
        self,
        tenant_client: AsyncClient,
        mock_tenant_service: AsyncMock,
        mock_tenant_organisation: str,
    ):
        """
        GIVEN the application is running in the testing environment and the TenantService is correct
        WHEN a HTTP POST request is made against '/api/v1/tenants' with the request parameters
        THEN a HTTP status code of 201 as well as the organisation name and status are returned
        """
        # 1. Arrange
        mock_service_response = TenantResponse(
            organisation=mock_tenant_organisation, status=TenantStatus.CREATED
        )
        mock_tenant_service.create.return_value = mock_service_response

        payload = {"organisation": "Test Organisation"}

        # 2. Act
        response = await tenant_client.post("/api/v1/tenants", json=payload)

        # 3. Assert
        assert response.status_code == status.HTTP_201_CREATED
        response_json = response.json()
        assert response_json["organisation"] == mock_tenant_organisation
        assert response_json == mock_service_response.model_dump(mode="json")

        # assert business logic and verify the service was called once
        mock_tenant_service.create.assert_awaited_once_with(
            Tenant(organisation=mock_tenant_organisation)
        )

    async def test_create_new_tenant_and_handle_empty_paramater_returns_400_when_bad_request(
        self, tenant_client: AsyncClient
    ):
        """
        GIVEN the application is running in the testing environment and TenantService is correctly injected
        WHEN a HTTP POST request is made against '/api/v1/tenants' with the request parameters of 'organisation' being an empty string
        THEN a HTTP status code of 400 with the message that the parameter is missing is returned
        """
        # 1. Arrange
        payload = {"organisation": ""}

        # 2. Act
        response = await tenant_client.post("/api/v1/tenants", json=payload)

        # 3. Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "detail": "Missing required parameter 'organisation' name"
        }

    # ---------------------------------------------------------
    # GET /tenants/{tenant_id} (Download URL)
    # ---------------------------------------------------------
    async def test_get_tenant_by_id_returns_tenant_created_and_200_when_ok(
        self,
        tenant_client: AsyncClient,
        mock_tenant_service: AsyncMock,
        mock_tenant_organisation: str,
        mock_tenant_id: UUID,
    ):
        """
        GIVEN the application is running in the testing environment and TenantService is correctly injected
        WHEN a HTTP GET request is made against '/api/v1/tenants' with a correct tenant id as path parameter
        THEN a HTTP status code of 200 and the retrieved tenant are returned
        """
        # 1. Arrange
        mock_service_response = TenantResponse(
            organisation=mock_tenant_organisation, status=TenantStatus.CREATED
        )
        mock_tenant_service.get.return_value = mock_service_response

        # 2. Act
        response = await tenant_client.get(f"/api/v1/tenants/{mock_tenant_id}")

        # 3. Assert
        assert response.status_code == status.HTTP_200_OK
        response_json = response.json()
        assert response_json["organisation"] == mock_tenant_organisation
        assert response_json["status"] == TenantStatus.CREATED.value

        # assert business logic
        mock_tenant_service.get.assert_awaited_once_with(mock_tenant_id)

    async def test_get_tenant_by_id_returns_404_when_not_found(
        self,
        tenant_client: AsyncClient,
        mock_tenant_service: AsyncMock,
        mock_tenant_id: UUID,
    ):
        """
        GIVEN the application is running in the testing environment and the TenantService is correctly injected
        WHEN a HTTP GET request is made against '/api/v1/tenants' with a mocked tenant id that doesn't map to a database entry
        THEN a HTTP status code of 404 resource not found and the correct error message is returned
        """
        # 1. Arrange
        error_message = "The requested resource couldn't be found."
        mock_tenant_service.get.side_effect = TenantNotFoundException(mock_tenant_id)

        # 2. Act
        response = await tenant_client.get(f"/api/v1/tenants/{mock_tenant_id}")

        # 3. Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        response_json = response.json()
        assert response_json["error"] == "not_found"
        assert response_json["message"] == error_message

    async def test_get_tenant_by_id_returns_500_when_failure(
        self,
        tenant_client: AsyncClient,
        mock_tenant_service: AsyncMock,
        mock_tenant_id: UUID,
    ):
        """
        GIVEN the application is running in the testing environment and the TenantService is correctly injected
        WHEN a HTTP GET request is made against '/api/v1/tenants' with a mocked database exception
        THEN a HTTP status code of 500 internal error and the correct error message is returned
        """

        # 1. Arrange
        error_message = (
            f"Failed to read tenant information for '{mock_tenant_id}' in the database."
        )
        mock_tenant_service.get.side_effect = DatabaseInternalException(error_message)

        # 2. Act
        response = await tenant_client.get(f"/api/v1/tenants/{mock_tenant_id}")

        # 3. Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        response_json = response.json()
        assert response_json["error"] == "database_error"
        assert response_json["message"] == "Database operation failed."

    # async def test_get_tenant_by_id_returns_422_when_unprocessable(
    #     self,
    #     tenant_client: AsyncClient,
    # ):
    #     """
    #     GIVEN the application is running in the testing environment and TenantService is correctly injected
    #     WHEN a HTTP GET request is made against '/api/v1/tenants' with an incorrect tenant id as path parameter
    #     THEN a HTTP status code of 400 with the message bad request is returned
    #     """
    #     # 1. Arrange
    #     mock_tenant_id = "test-not-a-valid-uuid"

    #     # 2. Act
    #     response = await tenant_client.get(f"/api/v1/tenants/{mock_tenant_id}")

    #     # 3. Assert
    #     assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # ---------------------------------------------------------
    # PATCH /tenants/{tenant_id} (Download URL)
    # ---------------------------------------------------------
    async def test_update_tenant_by_id_returns_200_when_ok(
        self,
        tenant_client: AsyncClient,
        mock_tenant_service: AsyncMock,
        mock_tenant_organisation: str,
        mock_tenant_id: UUID,
    ):
        """
        GIVEN the application is running in the testing environment and the TenantService is correctly injected
        WHEN a HTTP PATCH request is made against '/api/v1/tenants' with the mocked tenant organisation
        THEN a HTTP status code of 200 and the updated tenant with status are returned
        """

        # 1. Arrange
        payload = {
            "organisation": mock_tenant_organisation,
        }
        mock_service_response = TenantResponse(
            organisation=mock_tenant_organisation, status=TenantStatus.CREATED
        )
        mock_tenant_service.update.return_value = mock_service_response

        # 2. Act
        response = await tenant_client.patch(
            f"/api/v1/tenants/{mock_tenant_id}", json=payload
        )

        # 3. Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "organisation": mock_tenant_organisation,
            "status": TenantStatus.CREATED.value,
        }
        # assert business logic
        mock_tenant_service.update.assert_awaited_once_with(
            UpdateTenant(
                tenant_id=mock_tenant_id, organisation=mock_tenant_organisation
            )
        )

    async def test_update_tenant_by_id_with_organisation_returns_400_when_bad_request(
        self,
        tenant_client: AsyncClient,
        mock_tenant_service: AsyncMock,
        mock_tenant_organisation: str,
        mock_tenant_id: UUID,
    ):
        """
        GIVEN the application is running in the testing environment and the TenantService is correctly injected
        WHEN a HTTP PATCH request is made against '/api/v1/tenants' with the mocked tenant organisation containing an empty string
        THEN a HTTP status code of 400 bad request with the correct error message is returned
        """

        # 1. Arrange
        payload = {
            "organisation": "",
        }

        # 2. Act
        response = await tenant_client.patch(
            f"/api/v1/tenants/{mock_tenant_id}", json=payload
        )

        # 3. Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "detail": "Missing required parameter 'organisation' name"
        }
