"""The authenticated caller."""

from dataclasses import dataclass
from uuid import UUID

from src.libs.enums.user import UserRole


@dataclass(frozen=True, slots=True)
class Principal:
    """The user of a verified access token, with the roles stored now."""

    user_id: UUID
    tenant_id: UUID
    roles: frozenset[UserRole]

    @property
    def is_admin(self) -> bool:
        """True if the user may administer its tenant."""
        return UserRole.ADMIN in self.roles
