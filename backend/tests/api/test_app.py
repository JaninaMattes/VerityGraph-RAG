"""Tests for the application wiring in src.main (middleware and lifespan)."""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from src import main
from src.api.middleware import REQUEST_ID_HEADER
from src.libs.core.config import Settings
from src.main import app, settings


class TestCors:
    """Only the configured frontend origin may call the API from a browser."""

    def preflight(self, origin: str):
        with TestClient(app) as client:
            return client.options(
                "/api/v1/info",
                headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
            )

    def test_frontend_origin_is_allowed(self):
        """
        GIVEN the configured FRONTEND_URL
        WHEN the browser sends a CORS preflight from that origin
        THEN the API allows the origin
        """
        origin = str(settings.frontend_url).rstrip("/")

        response = self.preflight(origin)

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin

    def test_other_origin_is_rejected(self):
        """
        GIVEN an origin that is not the frontend
        WHEN the browser sends a CORS preflight
        THEN the API does not allow the origin
        """
        response = self.preflight("https://evil.example")

        assert "access-control-allow-origin" not in response.headers


class TestRequestContext:
    """The application adds the request id middleware."""

    def test_response_has_request_id(self):
        """
        GIVEN the application
        WHEN any endpoint is called
        THEN the response carries an X-Request-ID header
        """
        with TestClient(app) as client:
            response = client.get("/api/v1/info")

        assert response.headers[REQUEST_ID_HEADER]


class TestLogFormat:
    """Development logs are readable; all other environments log JSON."""

    def test_json_logs_outside_development(self, test_settings: Settings):
        """
        GIVEN the environments development, testing and production
        WHEN the log format is chosen
        THEN only development uses console output
        """
        formats = {
            env: test_settings.model_copy(update={"environment": env}).log_json
            for env in ("development", "testing", "production")
        }

        assert formats == {"development": False, "testing": True, "production": True}


class TestLifespan:
    """Startup creates the shared clients once; shutdown releases them."""

    async def test_startup_creates_one_storage_client(self, test_settings: Settings):
        """
        GIVEN the application
        WHEN it starts and stops
        THEN app.state holds one MinIO client for all requests
        AND the database engine is disposed at shutdown
        """
        engine = MagicMock(dispose=AsyncMock())
        client = MagicMock()

        with (
            patch.object(main, "create_async_db_engine", return_value=engine),
            patch.object(main, "create_storage_client", return_value=client) as create,
        ):
            async with main.lifespan(main.app):
                assert main.app.state.storage_client is client

        create.assert_called_once_with(main.settings)
        engine.dispose.assert_awaited_once()
