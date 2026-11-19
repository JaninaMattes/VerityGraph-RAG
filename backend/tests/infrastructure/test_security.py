"""Tests for password hashing and access tokens."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from src.domain.auth.entities import Principal
from src.infrastructure.security.passwords import Argon2PasswordHasher
from src.infrastructure.security.tokens import (
    create_access_token,
    decode_access_token,
)
from src.libs.core.config import Settings
from src.libs.enums.user import UserRole
from src.libs.exceptions.exceptions import AuthenticationException

PASSWORD = "correct horse battery"
PRINCIPAL = Principal(
    user_id=uuid.uuid4(), tenant_id=uuid.uuid4(), roles=frozenset({UserRole.ADMIN})
)


@pytest.fixture(scope="module")
def hasher() -> Argon2PasswordHasher:
    return Argon2PasswordHasher()


def sign(settings: Settings, **overrides: Any) -> str:
    """Sign valid claims for PRINCIPAL; a value of None removes that claim."""
    now = datetime.now(UTC)
    claims = {
        "sub": str(PRINCIPAL.user_id),
        "tid": str(PRINCIPAL.tenant_id),
        "roles": ["admin"],
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    key = overrides.pop("key", settings.secret_key.get_secret_value())
    algorithm = overrides.pop("algorithm", "HS256")
    claims.update(overrides)
    claims = {name: value for name, value in claims.items() if value is not None}
    return jwt.encode(claims, key, algorithm=algorithm)


class TestPasswordHasher:
    """Passwords are stored as salted Argon2id hashes."""

    def test_hash_verifies_only_the_same_password(self, hasher):
        """
        GIVEN a password
        WHEN it is hashed
        THEN the hash is Argon2id AND does not contain the password
        AND only the same password verifies against it
        """
        password_hash = hasher.hash(PASSWORD)

        assert password_hash.startswith("$argon2id$")
        assert PASSWORD not in password_hash
        assert hasher.verify(PASSWORD, password_hash) is True
        assert hasher.verify("wrong horse battery", password_hash) is False

    def test_same_password_gets_different_hashes(self, hasher):
        """
        GIVEN one password
        WHEN it is hashed twice
        THEN the hashes differ (each has its own salt)
        """
        assert hasher.hash(PASSWORD) != hasher.hash(PASSWORD)

    @pytest.mark.parametrize(
        "password_hash", [None, "", "not-a-hash"], ids=["none", "empty", "malformed"]
    )
    def test_missing_or_malformed_hash_never_verifies(self, hasher, password_hash):
        """
        GIVEN no hash (unknown user) or a malformed stored hash
        WHEN a password is verified against it
        THEN the result is False and no error is raised
        """
        assert hasher.verify(PASSWORD, password_hash) is False


class TestAccessToken:
    """Access tokens carry the user and tenant and are checked strictly."""

    def test_token_round_trip(self, test_settings: Settings):
        """
        GIVEN a principal
        WHEN a token is created and decoded with the same settings
        THEN the decoded user and tenant are those of the principal
        """
        token = create_access_token(PRINCIPAL, test_settings)

        assert decode_access_token(token, test_settings) == (
            PRINCIPAL.user_id,
            PRINCIPAL.tenant_id,
        )

    def test_token_claims_and_lifetime(self, test_settings: Settings):
        """
        GIVEN a principal
        WHEN a token is created
        THEN it names the user, tenant and roles
        AND it expires after access_token_expire_minutes
        """
        token = create_access_token(PRINCIPAL, test_settings)

        claims = jwt.decode(
            token, test_settings.secret_key.get_secret_value(), algorithms=["HS256"]
        )
        assert claims["sub"] == str(PRINCIPAL.user_id)
        assert claims["tid"] == str(PRINCIPAL.tenant_id)
        assert claims["roles"] == ["admin"]
        lifetime = test_settings.access_token_expire_minutes * 60
        assert claims["exp"] - claims["iat"] == lifetime

    @pytest.mark.parametrize(
        "overrides",
        [
            {"exp": datetime.now(UTC) - timedelta(seconds=1)},
            {"key": "another-secret-key-of-32-characters!!"},
            {"algorithm": "HS512"},
            {"algorithm": "none", "key": None},
            {"sub": None},
            {"tid": None},
            {"exp": None},
            {"iat": None},
            {"sub": "not-a-uuid"},
            {"tid": "not-a-uuid"},
        ],
        ids=[
            "expired",
            "wrong-key",
            "other-algorithm",
            "alg-none",
            "no-sub",
            "no-tid",
            "no-exp",
            "no-iat",
            "sub-not-uuid",
            "tid-not-uuid",
        ],
    )
    def test_invalid_token_is_rejected(self, test_settings: Settings, overrides):
        """
        GIVEN a token that is expired, forged, unsigned or has missing or bad claims
        WHEN it is decoded
        THEN AuthenticationException is raised
        """
        token = sign(test_settings, **overrides)

        with pytest.raises(AuthenticationException):
            decode_access_token(token, test_settings)

    @pytest.mark.parametrize(
        "token", ["", "abc", "a.b.c"], ids=["empty", "junk", "dots"]
    )
    def test_malformed_token_is_rejected(self, test_settings: Settings, token):
        """
        GIVEN a string that is not a JWT
        WHEN it is decoded
        THEN AuthenticationException is raised
        """
        with pytest.raises(AuthenticationException):
            decode_access_token(token, test_settings)
