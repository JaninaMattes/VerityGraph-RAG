"""Tests for the authentication use cases."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from src.domain.auth.entities import Principal
from src.domain.auth.service import AuthService
from src.domain.users.entities import UserEntity
from src.domain.users.repository import UserRepository
from src.libs.enums.user import UserRole, UserStatus
from src.libs.exceptions.exceptions import (
    AuthenticationException,
    UserNotFoundException,
)

PASSWORD = "correct horse battery"


class FakeHasher:
    """Hashes by prefixing; records every verification."""

    def __init__(self) -> None:
        self.verified: list[tuple[str, str | None]] = []

    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, password_hash: str | None) -> bool:
        self.verified.append((password, password_hash))
        return password_hash == f"hashed:{password}"


@pytest.fixture
def repository() -> AsyncMock:
    return AsyncMock(spec=UserRepository)


@pytest.fixture
def hasher() -> FakeHasher:
    return FakeHasher()


@pytest.fixture
def service(repository: AsyncMock, hasher: FakeHasher) -> AuthService:
    return AuthService(user_repository=repository, hasher=hasher)


def other_user(user: UserEntity) -> UserEntity:
    """The same email address in another tenant."""
    now = datetime.now(UTC)
    return UserEntity(
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        username=user.username,
        email=user.email,
        roles=[UserRole.USER],
        created_at=now,
        updated_at=now,
        status=UserStatus.ACTIVE,
    )


class TestPrincipal:
    """A principal knows whether it may administer its tenant."""

    @pytest.mark.parametrize(
        ("roles", "is_admin"),
        [({UserRole.ADMIN}, True), ({UserRole.USER}, False), (set(), False)],
    )
    def test_is_admin(self, roles, is_admin):
        """
        GIVEN a principal with some roles
        WHEN is_admin is read
        THEN it is True only with the ADMIN role
        """
        principal = Principal(uuid.uuid4(), uuid.uuid4(), frozenset(roles))

        assert principal.is_admin is is_admin


class TestAuthenticate:
    """authenticate() checks an email and password and returns the principal."""

    async def test_valid_credentials_return_principal(
        self, service, repository, user_entity
    ):
        """
        GIVEN a user whose stored hash matches the password
        WHEN the user authenticates with email and password
        THEN the principal has the user's id, tenant and roles
        """
        repository.find_login_candidates.return_value = [
            (user_entity, f"hashed:{PASSWORD}")
        ]

        principal = await service.authenticate(user_entity.email, PASSWORD)

        repository.find_login_candidates.assert_awaited_once_with(user_entity.email)
        assert principal == Principal(
            user_entity.user_id, user_entity.tenant_id, frozenset(user_entity.roles)
        )

    async def test_email_is_compared_in_lower_case(self, service, repository):
        """
        GIVEN a login email in mixed case with surrounding spaces
        WHEN someone authenticates with it
        THEN the users are looked up by the trimmed, lower-case email
        """
        repository.find_login_candidates.return_value = []

        with pytest.raises(AuthenticationException):
            await service.authenticate("  Ada@Example.COM ", PASSWORD)

        repository.find_login_candidates.assert_awaited_once_with("ada@example.com")

    async def test_unknown_email_is_rejected_after_dummy_verification(
        self, service, repository, hasher
    ):
        """
        GIVEN no user with the email
        WHEN someone authenticates with it
        THEN AuthenticationException is raised
        AND a password check still runs, so the timing does not reveal the email
        """
        repository.find_login_candidates.return_value = []

        with pytest.raises(AuthenticationException):
            await service.authenticate("nobody@example.com", PASSWORD)

        assert hasher.verified == [(PASSWORD, None)]

    async def test_wrong_password_is_rejected(self, service, repository, user_entity):
        """
        GIVEN a user
        WHEN someone authenticates with a wrong password
        THEN AuthenticationException is raised
        """
        repository.find_login_candidates.return_value = [
            (user_entity, f"hashed:{PASSWORD}")
        ]

        with pytest.raises(AuthenticationException):
            await service.authenticate(user_entity.email, "wrong horse battery")

    async def test_password_selects_the_tenant_of_a_shared_email(
        self, service, repository, user_entity
    ):
        """
        GIVEN the same email in two tenants with different passwords
        WHEN the user authenticates with the password of the second tenant
        THEN the principal is the user of the second tenant
        """
        second = other_user(user_entity)
        repository.find_login_candidates.return_value = [
            (user_entity, "hashed:another password"),
            (second, f"hashed:{PASSWORD}"),
        ]

        principal = await service.authenticate(user_entity.email, PASSWORD)

        assert principal.tenant_id == second.tenant_id

    async def test_ambiguous_match_is_rejected(self, service, repository, user_entity):
        """
        GIVEN the same email and the same password in two tenants
        WHEN the user authenticates
        THEN AuthenticationException is raised (the tenant is ambiguous)
        """
        repository.find_login_candidates.return_value = [
            (user_entity, f"hashed:{PASSWORD}"),
            (other_user(user_entity), f"hashed:{PASSWORD}"),
        ]

        with pytest.raises(AuthenticationException):
            await service.authenticate(user_entity.email, PASSWORD)


class TestResolve:
    """resolve() turns the ids of a verified token into a current principal."""

    async def test_active_user_resolves_with_current_roles(
        self, service, repository, user_entity
    ):
        """
        GIVEN a user that exists and is not disabled
        WHEN its token ids are resolved
        THEN the principal has the roles stored now, not those in the token
        """
        user_entity.roles = [UserRole.ADMIN]
        repository.get_one.return_value = user_entity

        principal = await service.resolve(user_entity.user_id, user_entity.tenant_id)

        repository.get_one.assert_awaited_once_with(
            user_entity.user_id, user_entity.tenant_id
        )
        assert principal.is_admin

    async def test_missing_user_is_rejected(self, service, repository):
        """
        GIVEN a token of a user that no longer exists
        WHEN its ids are resolved
        THEN AuthenticationException is raised (401, not 404)
        """
        user_id = uuid.uuid4()
        repository.get_one.side_effect = UserNotFoundException(user_id)

        with pytest.raises(AuthenticationException):
            await service.resolve(user_id, uuid.uuid4())

    async def test_disabled_user_is_rejected(self, service, repository, user_entity):
        """
        GIVEN a user that was disabled after the token was issued
        WHEN its ids are resolved
        THEN AuthenticationException is raised
        """
        user_entity.status = UserStatus.DISABLED
        repository.get_one.return_value = user_entity

        with pytest.raises(AuthenticationException):
            await service.resolve(user_entity.user_id, user_entity.tenant_id)

    async def test_deleted_user_is_rejected(self, service, repository, user_entity):
        """
        GIVEN a user that is marked as deleted
        WHEN its ids are resolved
        THEN AuthenticationException is raised
        """
        user_entity.deleted_at = datetime.now(UTC)
        repository.get_one.return_value = user_entity

        with pytest.raises(AuthenticationException):
            await service.resolve(user_entity.user_id, user_entity.tenant_id)
