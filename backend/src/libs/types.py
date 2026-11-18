"""Shared Pydantic field types."""

from typing import Annotated

from pydantic import StringConstraints

# A string with at least one non-blank character. Surrounding whitespace is removed.
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
