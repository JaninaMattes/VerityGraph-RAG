"""Tests for the /users endpoints."""

from unittest.mock import AsyncMock

import pytest
from fastapi import status
from httpx import AsyncClient
from src.domain.users.dataclasses import UpdateUser, User
from src.libs.exceptions.exceptions import (
    ConflictException,
    UserNotFoundException,
)

PASSWORD = "correct horse battery"
USER_BODY = {"username": "ada", "email": "ada@example.com", "password": PASSWORD}


def user_json(entity) -> dict:
    return {
        "user_id": str(entity.user_id),
        "username": entity.username,
        "email": entity.email,
        "status": entity.status.value,
    }


class TestRegisterUser:
    """POST /users registers a user in the caller's tenant."""

    async def test_returns_201_and_user(
        self,
        api_client: AsyncClient,
        mock_user_service: AsyncMock,
        user_entity,
        mock_tenant_id,
    ):
        """
        GIVEN a valid username, email and password
        WHEN POST /api/v1/users is called
        THEN the response is 201 with the user AND the user is created in the caller's tenant
        """
        mock_user_service.create.return_value = user_entity

        response = await api_client.post("/api/v1/users", json=USER_BODY)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.json() == user_json(user_entity)
        mock_user_service.create.assert_awaited_once_with(
            User("ada", "ada@example.com", PASSWORD), mock_tenant_id
        )

    @pytest.mark.parametrize(
        "override",
        [
            {"username": ""},
            {"username": "  "},
            {"email": ""},
            {"password": None},
            {"password": "short"},
            {"password": "x" * 129},
            {"roles": ["admin"]},
        ],
        ids=[
            "empty-username",
            "blank-username",
            "empty-email",
            "missing-password",
            "short-password",
            "long-password",
            "extra-field",
        ],
    )
    async def test_invalid_body_returns_422(
        self, api_client: AsyncClient, mock_user_service: AsyncMock, override
    ):
        """
        GIVEN a body with a missing, empty or blank required field
        WHEN POST /api/v1/users is called
        THEN the response is 422 AND the service is not called
        """
        body = {
            key: value
            for key, value in (USER_BODY | override).items()
            if value is not None
        }

        response = await api_client.post("/api/v1/users", json=body)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        mock_user_service.create.assert_not_awaited()

    async def test_duplicate_returns_409(
        self, api_client: AsyncClient, mock_user_service: AsyncMock
    ):
        """
        GIVEN the email exists already
        WHEN POST /api/v1/users is called
        THEN the response is 409 with the conflict error body
        """
        mock_user_service.create.side_effect = ConflictException("duplicate")

        response = await api_client.post("/api/v1/users", json=USER_BODY)

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json()["error"] == "conflict"


class TestReadUser:
    """GET /users/{user_id} returns a user of the caller's tenant."""

    async def test_returns_200_and_user(
        self,
        api_client: AsyncClient,
        mock_user_service: AsyncMock,
        user_entity,
        mock_tenant_id,
    ):
        """
        GIVEN an existing user
        WHEN GET /api/v1/users/{id} is called
        THEN the response is 200 with the user
        """
        mock_user_service.get.return_value = user_entity

        response = await api_client.get(f"/api/v1/users/{user_entity.user_id}")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == user_json(user_entity)
        mock_user_service.get.assert_awaited_once_with(
            user_entity.user_id, mock_tenant_id
        )

    async def test_missing_user_returns_404(
        self, api_client: AsyncClient, mock_user_service: AsyncMock, mock_user_id
    ):
        """
        GIVEN the user does not exist in the caller's tenant
        WHEN GET /api/v1/users/{id} is called
        THEN the response is 404
        """
        mock_user_service.get.side_effect = UserNotFoundException(mock_user_id)

        response = await api_client.get(f"/api/v1/users/{mock_user_id}")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestUpdateUser:
    """PATCH /users/{user_id} changes the username and email."""

    async def test_returns_200_and_updated_user(
        self,
        api_client: AsyncClient,
        mock_user_service: AsyncMock,
        user_entity,
        mock_tenant_id,
    ):
        """
        GIVEN an existing user and a new username and email
        WHEN PATCH /api/v1/users/{id} is called
        THEN the response is 200 AND the service receives the update for the caller's tenant
        """
        mock_user_service.update.return_value = user_entity

        response = await api_client.patch(
            f"/api/v1/users/{user_entity.user_id}",
            json={"username": "grace", "email": "g@example.com"},
        )

        assert response.status_code == status.HTTP_200_OK
        mock_user_service.update.assert_awaited_once_with(
            UpdateUser(user_entity.user_id, mock_tenant_id, "grace", "g@example.com")
        )

    @pytest.mark.parametrize(
        "body",
        [
            {"username": "", "email": "g@example.com"},
            {"username": "grace", "email": " "},
        ],
        ids=["empty-username", "blank-email"],
    )
    async def test_blank_field_returns_422(
        self, api_client: AsyncClient, mock_user_service: AsyncMock, mock_user_id, body
    ):
        """
        GIVEN an empty or blank username or email
        WHEN PATCH /api/v1/users/{id} is called
        THEN the response is 422 AND the service is not called
        """
        response = await api_client.patch(f"/api/v1/users/{mock_user_id}", json=body)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        mock_user_service.update.assert_not_awaited()


class TestDeactivateUser:
    """DELETE /users/{user_id} removes a user of the caller's tenant."""

    async def test_returns_204(
        self,
        api_client: AsyncClient,
        mock_user_service: AsyncMock,
        mock_user_id,
        mock_tenant_id,
    ):
        """
        GIVEN an existing user
        WHEN DELETE /api/v1/users/{id} is called
        THEN the response is 204 AND the service deletes the user in the caller's tenant
        """
        response = await api_client.delete(f"/api/v1/users/{mock_user_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock_user_service.delete.assert_awaited_once_with(mock_user_id, mock_tenant_id)
