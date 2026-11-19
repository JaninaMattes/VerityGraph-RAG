"""PasswordHasher adapter: Argon2id through pwdlib."""

import secrets
from functools import cached_property

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.argon2 import Argon2Hasher

from src.domain.auth.hasher import PasswordHasher


class Argon2PasswordHasher(PasswordHasher):
    """Argon2id with pwdlib's defaults (64 MiB, 3 passes). Create one per process."""

    def __init__(self) -> None:
        self._context = PasswordHash((Argon2Hasher(),))

    @cached_property
    def _dummy_hash(self) -> str:
        """A hash of a random password, checked when the user does not exist."""
        return self._context.hash(secrets.token_urlsafe(16))

    def hash(self, password: str) -> str:
        return self._context.hash(password)

    def verify(self, password: str, password_hash: str | None) -> bool:
        if not password_hash:
            self._context.verify(password, self._dummy_hash)
            return False
        try:
            return self._context.verify(password, password_hash)
        except UnknownHashError:
            return False
