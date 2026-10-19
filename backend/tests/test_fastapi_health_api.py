import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx import AsyncClient
from src.api.dependencies import get_settings
from src.libs.schemas.health import AppHealthResponse
from src.main import app

# Apply to all tests in this module
pytestmark = pytest.mark.asyncio

# ==========================================================
# Endpoint: POST /health (receive app name)
# ==========================================================


class TestHealthAPIEndpoints:
    """
    Test suite for the Health and Info API endpoints.
    Ensures the application correctly reports its configuration state.
    """

    # ---------------------------------------------------------
    # GET /info/
    # ---------------------------------------------------------

    async def test_get_health_info_returns_200_and_correct_app_name(
        self,
        client: AsyncClient,
    ):
        """
        GIVEN the application is running in the testing environment
        WHEN a GET request is made to '/api/v1/info'
        THEN it should return 200 OK and the configured app_name.
        """

        # 1. Arrange
        expected_app_name = "Graph RAG Backend"
        expected_response = AppHealthResponse(app_name=expected_app_name)

        # 2. Act
        response = await client.get("/api/v1/info")

        # 3. Assert
        assert response.status_code == status.HTTP_200_OK
        response_json = response.json()

        # Not: Always assert specific field (e.g. app_name)
        assert response_json["app_name"] == expected_app_name
        assert response_json == expected_response.model_dump(mode="json")

    async def test_get_health_info_handles_missing_dependency_returns_500(
        self,
    ):
        """
        GIVEN the settings dependency is artificially broken
        WHEN a GET request is made to '/api/v1/health/info'
        THEN it should return a 500 Internal Server Error (or 422, depending on FastAPI validation).
        """

        # 1. Arrange
        def mock_broken_settings():
            raise ValueError("Simulated configuration failure")

        app.dependency_overrides[get_settings] = mock_broken_settings

        try:
            # 2. Act
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get("/api/v1/info")

            # 3. Assert
            # FastAPI should catch the ValueError and return a 500 Internal Server Error
            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        finally:
            # Cleanup
            app.dependency_overrides.pop(get_settings, None)
