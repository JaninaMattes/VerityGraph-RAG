from dataclasses import dataclass, field
from uuid import UUID


@dataclass(slots=True, frozen=True)
class User:
    """
    Domain representation of a new user object.
    """

    username: str
    email: str
    password: str = field(repr=False)  # plain text; hashed by UserService


@dataclass(slots=True, frozen=True)
class UpdateUser:
    """
    Domain representation of an updated user object.
    """

    user_id: UUID
    tenant_id: UUID
    username: str
    email: str
