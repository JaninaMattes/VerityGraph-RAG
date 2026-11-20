"""Shared Pydantic field types."""

import unicodedata
from typing import Annotated

from pydantic import AfterValidator, EmailStr, StringConstraints


def _without_control_characters(value: str) -> str:
    """Reject NUL (Postgres cannot store it) and other control characters."""
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError("must not contain control characters")
    return value


# 1 to 255 characters (the column size), trimmed, without control characters.
NonEmptyStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
    AfterValidator(_without_control_characters),
]

# A valid address, in lower case, so that login can compare it exactly.
Email = Annotated[EmailStr, AfterValidator(str.lower)]
