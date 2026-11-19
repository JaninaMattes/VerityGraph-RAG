"""Tests for login and for the authentication and roles on every endpoint."""

import re
import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import status
from httpx import AsyncClient

from src.api.rate_limit import RateLimiter
from src.domain.auth.entities import Principal
from src.infrastructure.security.tokens import (
    create_access_token,
    decode_access_token,
)
from src.libs.core.config import Settings
from src.libs.exceptions.exceptions import AuthenticationException
from src.main import app

PASSWORD = "correct horse battery"
PUBLIC_ROUTES = {
    ("GET", "/api/v1/info"),
    ("GET", "/api/v1/health/live"),
    ("GET", "/api/v1/health/ready"),
    ("POST", "/api/v1/auth/token"),
}
ADMIN_ROUTES = [
    ("POST", "/api/v1/tenants"),
    ("PATCH", "/api/v1/tenants/{tenant_id}"),
    ("DELETE", "/api/v1/tenants/{tenant_id}"),
    ("POST", "/api/v1/users"),
    ("DELETE", "/api/v1/users/{user_id}"),
]
# Valid for every route, so a test reaches the authentication check.
ANY_BODY = {
    "organisation": "ACME",
    "username": "ada",
    "email": "ada@example.com",
    "password": PASSWORD,
    "filename": "report.pdf",
}


def all_routes() -> set[tuple[str, str]]:
    """Every (method, path) of the app, read from its OpenAPI schema."""
    return {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }


def protected_routes() -> list[tuple[str, str]]:
    return sorted(all_routes() - PUBLIC_ROUTES)


def concrete(path: str, value: uuid.UUID | None = None) -> str:
    """Fill every path parameter with `value` (a new UUID by default)."""
    return re.sub(r"\{[^}]+\}", str(value or uuid.uuid4()), path)


def assert_unauthenticated(response) -> None:
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json() == {
        "error": "not_authenticated",
        "message": "Authentication is required.",
    }


class TestLogin:
    """POST /auth/token exchanges an email and password for a bearer token."""

    async def test_valid_credentials_return_bearer_token(
        self,
        client: AsyncClient,
        mock_auth_service: AsyncMock,
        principal: Principal,
        test_settings: Settings,
    ):
        """
        GIVEN a user with this email and password
        WHEN the form is posted to /auth/token
        THEN the response is a bearer token for that user and tenant
        AND it states the lifetime in seconds
        """
        mock_auth_service.authenticate.return_value = principal

        response = await client.post(
            "/api/v1/auth/token",
            data={"username": "ada@example.com", "password": PASSWORD},
        )

        assert response.status_code == status.HTTP_200_OK
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == test_settings.access_token_expire_minutes * 60
        assert decode_access_token(body["access_token"], test_settings) == (
            principal.user_id,
            principal.tenant_id,
        )
        mock_auth_service.authenticate.assert_awaited_once_with(
            "ada@example.com", PASSWORD
        )

    async def test_wrong_credentials_return_401_without_reason(
        self, client: AsyncClient, mock_auth_service: AsyncMock
    ):
        """
        GIVEN an unknown email or a wrong password
        WHEN the form is posted to /auth/token
        THEN the response is the generic 401, which does not say which one was wrong
        """
        mock_auth_service.authenticate.side_effect = AuthenticationException(
            "Unknown email."
        )

        response = await client.post(
            "/api/v1/auth/token",
            data={"username": "nobody@example.com", "password": PASSWORD},
        )

        assert_unauthenticated(response)

    @pytest.mark.parametrize(
        "form",
        [{}, {"username": "ada@example.com"}, {"password": PASSWORD}],
        ids=["empty", "no-password", "no-username"],
    )
    async def test_incomplete_form_returns_422(
        self, client: AsyncClient, mock_auth_service: AsyncMock, form
    ):
        """
        GIVEN a login form without username or password
        WHEN it is posted to /auth/token
        THEN the response is 422 AND no authentication is tried
        """
        response = await client.post("/api/v1/auth/token", data=form)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        mock_auth_service.authenticate.assert_not_awaited()

    async def test_too_many_attempts_return_429_without_password_check(
        self,
        client: AsyncClient,
        mock_auth_service: AsyncMock,
        login_limiter: RateLimiter,
    ):
        """
        GIVEN a client address that used all its login attempts in this minute
        WHEN it posts the login form again
        THEN the response is 429 with Retry-After
        AND the password is not checked (no Argon2 work for the attacker)
        """
        mock_auth_service.authenticate.side_effect = AuthenticationException("Wrong.")
        form = {"username": "ada@example.com", "password": PASSWORD}
        for _ in range(login_limiter.limit):
            await client.post("/api/v1/auth/token", data=form)
        mock_auth_service.authenticate.reset_mock()

        response = await client.post("/api/v1/auth/token", data=form)

        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert int(response.headers["Retry-After"]) >= 1
        assert response.json()["error"] == "too_many_requests"
        mock_auth_service.authenticate.assert_not_awaited()


class TestAuthenticationRequired:
    """Every endpoint except health and login needs a valid bearer token."""

    def test_public_routes_exist(self):
        """
        GIVEN the list of public routes
        WHEN it is compared with the routes of the app
        THEN every listed route exists AND other routes exist to protect
            (so the parametrized tests below can never run with zero cases)
        """
        assert PUBLIC_ROUTES <= all_routes()
        assert len(protected_routes()) >= 10

    @pytest.mark.parametrize(("method", "path"), protected_routes())
    async def test_request_without_token_returns_401(
        self, client: AsyncClient, method: str, path: str
    ):
        """
        GIVEN a protected route
        WHEN it is called without an Authorization header
        THEN the response is 401 with the Bearer challenge
        """
        response = await client.request(method, concrete(path), json=ANY_BODY)

        assert_unauthenticated(response)

    @pytest.mark.parametrize(
        "authorization",
        ["Bearer not-a-jwt", "Basic YWRhOnB3", "Bearer "],
        ids=["junk-token", "basic-scheme", "empty-token"],
    )
    async def test_invalid_authorization_returns_401(
        self, client: AsyncClient, mock_auth_service: AsyncMock, authorization: str
    ):
        """
        GIVEN a malformed token or another scheme
        WHEN a protected route is called with it
        THEN the response is 401 AND no user is looked up
        """
        response = await client.get(
            concrete("/api/v1/documents/{document_id}/chunks"),
            headers={"Authorization": authorization},
        )

        assert_unauthenticated(response)
        mock_auth_service.resolve.assert_not_awaited()

    async def test_valid_token_scopes_the_request_to_its_tenant(
        self,
        client: AsyncClient,
        mock_auth_service: AsyncMock,
        mock_chunk_service: AsyncMock,
        principal: Principal,
        test_settings: Settings,
    ):
        """
        GIVEN a valid token of an existing user
        WHEN a protected route is called with it
        THEN the user is looked up by the token's ids
        AND the service works in the token's tenant
        """
        mock_auth_service.resolve.return_value = principal
        mock_chunk_service.list_for_document.return_value = []
        document_id = uuid.uuid4()
        token = create_access_token(principal, test_settings)

        response = await client.get(
            f"/api/v1/documents/{document_id}/chunks",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        mock_auth_service.resolve.assert_awaited_once_with(
            principal.user_id, principal.tenant_id
        )
        mock_chunk_service.list_for_document.assert_awaited_once_with(
            document_id, principal.tenant_id, limit=100, offset=0
        )

    async def test_token_of_disabled_user_returns_401(
        self,
        client: AsyncClient,
        mock_auth_service: AsyncMock,
        principal: Principal,
        test_settings: Settings,
    ):
        """
        GIVEN a valid token of a user that was disabled after login
        WHEN a protected route is called with it
        THEN the response is 401
        """
        mock_auth_service.resolve.side_effect = AuthenticationException("disabled")
        token = create_access_token(principal, test_settings)

        response = await client.get(
            concrete("/api/v1/documents/{document_id}/chunks"),
            headers={"Authorization": f"Bearer {token}"},
        )

        assert_unauthenticated(response)


class TestRoles:
    """Changing the tenant and its users needs the admin role."""

    @pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
    async def test_member_gets_403_on_admin_routes(
        self, api_client: AsyncClient, as_member: Principal, method: str, path: str
    ):
        """
        GIVEN a caller without the admin role
        WHEN it calls a route that changes the tenant or its users
        THEN the response is 403
        """
        response = await api_client.request(
            method, concrete(path, as_member.tenant_id), json=ANY_BODY
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json()["error"] == "forbidden"

    async def test_member_may_update_itself(
        self,
        api_client: AsyncClient,
        as_member: Principal,
        mock_user_service: AsyncMock,
        user_entity,
    ):
        """
        GIVEN a caller without the admin role
        WHEN it changes its own username and email
        THEN the response is 200
        """
        mock_user_service.update.return_value = user_entity

        response = await api_client.patch(
            f"/api/v1/users/{as_member.user_id}",
            json={"username": "ada", "email": "ada@example.com"},
        )

        assert response.status_code == status.HTTP_200_OK

    async def test_member_may_not_update_another_user(
        self,
        api_client: AsyncClient,
        as_member: Principal,
        mock_user_service: AsyncMock,
    ):
        """
        GIVEN a caller without the admin role
        WHEN it changes another user of its tenant
        THEN the response is 403 AND nothing is changed
        """
        response = await api_client.patch(
            f"/api/v1/users/{uuid.uuid4()}",
            json={"username": "eve", "email": "eve@example.com"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        mock_user_service.update.assert_not_awaited()
