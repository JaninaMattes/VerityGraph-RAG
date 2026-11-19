"""Tests for the /tenants endpoints."""

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from httpx import AsyncClient

from src.domain.tenants.dataclasses import Tenant, UpdateTenant
from src.libs.enums.tenant import TenantStatus
from src.libs.exceptions.exceptions import (
    DatabaseException,
    TenantNotFoundException,
)

NOT_FOUND = {
    "error": "not_found",
    "message": "The requested resource couldn't be found.",
}


class TestCreateTenant:
    """POST /tenants creates a tenant."""

    async def test_returns_201_and_tenant(
        self, api_client: AsyncClient, mock_tenant_service: AsyncMock, tenant_entity
    ):
        """
        GIVEN a valid organisation name
        WHEN POST /api/v1/tenants is called
        THEN the response is 201 with the organisation and status
        """
        mock_tenant_service.create.return_value = tenant_entity

        response = await api_client.post(
            "/api/v1/tenants", json={"organisation": tenant_entity.organisation}
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == {
            "organisation": tenant_entity.organisation,
            "status": TenantStatus.CREATED.value,
        }
        mock_tenant_service.create.assert_awaited_once_with(
            Tenant(organisation=tenant_entity.organisation)
        )

    @pytest.mark.parametrize("organisation", ["", "   "], ids=["empty", "blank"])
    async def test_blank_organisation_returns_422(
        self, api_client: AsyncClient, mock_tenant_service: AsyncMock, organisation
    ):
        """
        GIVEN an empty or blank organisation name
        WHEN POST /api/v1/tenants is called
        THEN the response is 422 AND the service is not called
        """
        response = await api_client.post(
            "/api/v1/tenants", json={"organisation": organisation}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        mock_tenant_service.create.assert_not_awaited()


class TestReadTenant:
    """GET /tenants/{tenant_id} returns the caller's own tenant only."""

    async def test_own_tenant_returns_200(
        self, api_client: AsyncClient, mock_tenant_service: AsyncMock, tenant_entity
    ):
        """
        GIVEN the path id is the caller's tenant
        WHEN GET /api/v1/tenants/{id} is called
        THEN the response is 200 with the tenant
        """
        mock_tenant_service.get.return_value = tenant_entity

        response = await api_client.get(f"/api/v1/tenants/{tenant_entity.tenant_id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["organisation"] == tenant_entity.organisation
        mock_tenant_service.get.assert_awaited_once_with(tenant_entity.tenant_id)

    async def test_other_tenant_returns_404(
        self, api_client: AsyncClient, mock_tenant_service: AsyncMock
    ):
        """
        GIVEN the path id is a different tenant than the caller's
        WHEN GET /api/v1/tenants/{id} is called
        THEN the response is 404 (existence is not revealed) AND the service is not called
        """
        response = await api_client.get(f"/api/v1/tenants/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == NOT_FOUND
        mock_tenant_service.get.assert_not_awaited()

    async def test_missing_tenant_returns_404(
        self, api_client: AsyncClient, mock_tenant_service: AsyncMock, mock_tenant_id
    ):
        """
        GIVEN the caller's tenant does not exist in the database
        WHEN GET /api/v1/tenants/{id} is called
        THEN the response is 404 with the standard error body
        """
        mock_tenant_service.get.side_effect = TenantNotFoundException(mock_tenant_id)

        response = await api_client.get(f"/api/v1/tenants/{mock_tenant_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == NOT_FOUND

    async def test_database_failure_returns_500(
        self, api_client: AsyncClient, mock_tenant_service: AsyncMock, mock_tenant_id
    ):
        """
        GIVEN the database fails
        WHEN GET /api/v1/tenants/{id} is called
        THEN the response is 500 with the database error body
        """
        mock_tenant_service.get.side_effect = DatabaseException("db down")

        response = await api_client.get(f"/api/v1/tenants/{mock_tenant_id}")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.json() == {
            "error": "database_error",
            "message": "Database operation failed.",
        }

    async def test_invalid_id_returns_422(self, api_client: AsyncClient):
        """
        GIVEN a path id that is not a UUID
        WHEN GET /api/v1/tenants/{id} is called
        THEN the response is 422
        """
        response = await api_client.get("/api/v1/tenants/not-a-uuid")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestUpdateTenant:
    """PATCH /tenants/{tenant_id} renames the caller's own tenant."""

    async def test_own_tenant_returns_200(
        self, api_client: AsyncClient, mock_tenant_service: AsyncMock, tenant_entity
    ):
        """
        GIVEN the path id is the caller's tenant and a new organisation name
        WHEN PATCH /api/v1/tenants/{id} is called
        THEN the response is 200 AND the service receives the update
        """
        mock_tenant_service.update.return_value = tenant_entity

        response = await api_client.patch(
            f"/api/v1/tenants/{tenant_entity.tenant_id}", json={"organisation": "New"}
        )

        assert response.status_code == status.HTTP_200_OK
        mock_tenant_service.update.assert_awaited_once_with(
            UpdateTenant(tenant_id=tenant_entity.tenant_id, organisation="New")
        )

    async def test_other_tenant_returns_404(
        self, api_client: AsyncClient, mock_tenant_service: AsyncMock
    ):
        """
        GIVEN the path id is a different tenant than the caller's
        WHEN PATCH /api/v1/tenants/{id} is called
        THEN the response is 404 AND the service is not called
        """
        response = await api_client.patch(
            f"/api/v1/tenants/{uuid.uuid4()}", json={"organisation": "New"}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        mock_tenant_service.update.assert_not_awaited()

    async def test_blank_organisation_returns_422(
        self, api_client: AsyncClient, mock_tenant_id
    ):
        """
        GIVEN an empty organisation name
        WHEN PATCH /api/v1/tenants/{id} is called
        THEN the response is 422
        """
        response = await api_client.patch(
            f"/api/v1/tenants/{mock_tenant_id}", json={"organisation": ""}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestRevokeTenant:
    """DELETE /tenants/{tenant_id} removes the caller's own tenant."""

    async def test_own_tenant_returns_204(
        self, api_client: AsyncClient, mock_tenant_service: AsyncMock, mock_tenant_id
    ):
        """
        GIVEN the path id is the caller's tenant
        WHEN DELETE /api/v1/tenants/{id} is called
        THEN the response is 204 AND the service deletes that tenant
        """
        response = await api_client.delete(f"/api/v1/tenants/{mock_tenant_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock_tenant_service.delete.assert_awaited_once_with(mock_tenant_id)

    async def test_other_tenant_returns_404(
        self, api_client: AsyncClient, mock_tenant_service: AsyncMock
    ):
        """
        GIVEN the path id is a different tenant than the caller's
        WHEN DELETE /api/v1/tenants/{id} is called
        THEN the response is 404 AND nothing is deleted
        """
        response = await api_client.delete(f"/api/v1/tenants/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        mock_tenant_service.delete.assert_not_awaited()
