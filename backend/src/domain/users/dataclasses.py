from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True, frozen=True)
class User:
    """
    Domain representation of a new user object.
    """

    username: str
    email: str
    password_hash: str


@dataclass(slots=True, frozen=True)
class UpdateUser:
    """
    Domain representation of an updated user object.
    """

    user_id: UUID
    username: str
    email: str