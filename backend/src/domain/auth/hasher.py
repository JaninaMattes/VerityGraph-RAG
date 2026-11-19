"""Port for password hashing."""

from typing import Protocol


class PasswordHasher(Protocol):
    """Hashes passwords and checks a password against a stored hash."""

    def hash(self, password: str) -> str:
        """Return a salted hash of `password`."""
        raise NotImplementedError

    def verify(self, password: str, password_hash: str | None) -> bool:
        """Return True if `password` matches `password_hash`.

        A missing or malformed hash returns False after a full-cost check, so the
        time does not reveal whether the user exists.
        """
        raise NotImplementedError
