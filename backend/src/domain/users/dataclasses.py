from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class User:
    """
    Domain representation of a new user object.
    """

    username: str
    email: str
