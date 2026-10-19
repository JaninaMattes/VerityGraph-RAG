from unittest.mock import AsyncMock

import pytest
from fastapi import status
from httpx import AsyncClient
from src.libs.enums.tenant import TenantStatus
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
        assert response.json() == mock_service_response.model_dump(mode="json")

    async def test_create_new_tenant_and_handle_empty_paramater_returns_400(
        self, tenant_client: AsyncClient
    ):
        """
        GIVEN the application is running in the testing environment and the TenantService is correct
        WHEN a HTTP POST request is made against '/api/v1/tenants' with the request parameters of 'organisation' being empty
        THEN a HTTP status code of 400 with the message that the parameter is missing is returned
        """
        # 1. Arrange
        payload = {"organisation": ""}

        # 2. Act
        response = await tenant_client.post("/api/v1/tenants", json=payload)

        # 3. Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error_details = response.json()["detail"]
        assert any(err["loc"] == ["body", "tenant"] for err in error_details)
