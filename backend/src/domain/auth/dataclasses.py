from dataclasses import dataclass, field
from uuid import UUID

from src.shared.enums import UserRole


@dataclass(slots=True)
class TokenPayload:
    user_id: UUID
    session_id: UUID


@dataclass(slots=True, frozen=True)
class Principal:
    """Authenticated identity available throughout the request."""

    user_id: UUID
    tenant_id: UUID
    email: str
    roles: tuple[UserRole, ...] = field(default_factory=lambda: (UserRole.USER,))


@dataclass(slots=True, frozen=True)
class LoginCredentials: ...


@dataclass(slots=True, frozen=True)
class PasswordResetToken: ...


@dataclass(slots=True, frozen=True)
class TokenPair: ...


@dataclass(slots=True, frozen=True)
class RefreshSession: ...
