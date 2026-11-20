"""Signed access tokens (JWT). Only the configured HMAC algorithm is accepted."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from src.domain.auth.entities import Principal
from src.libs.core.config import Settings
from src.libs.exceptions.exceptions import AuthenticationException

REQUIRED_CLAIMS = ["sub", "tid", "iat", "exp"]


def create_access_token(principal: Principal, settings: Settings) -> str:
    """Return a token for the principal that expires after the configured minutes.

    The roles are informational for clients; the API reads the current roles from
    the database on every request.
    """
    now = datetime.now(UTC)
    claims = {
        "sub": str(principal.user_id),
        "tid": str(principal.tenant_id),
        "roles": sorted(role.value for role in principal.roles),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(
        claims, settings.secret_key.get_secret_value(), algorithm=settings.algorithm
    )


def decode_access_token(token: str, settings: Settings) -> tuple[UUID, UUID]:
    """Return (user_id, tenant_id) of a valid token.

    Raise AuthenticationException if the token is malformed, signed with another key
    or algorithm (including 'none'), expired, or lacks a required claim.
    """
    try:
        claims = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            options={"require": REQUIRED_CLAIMS},
        )
        return UUID(claims["sub"]), UUID(claims["tid"])
    except (jwt.InvalidTokenError, ValueError, TypeError) as exc:
        raise AuthenticationException(f"Invalid access token: {exc}") from exc
