"""Tests for the request bodies: they reject input that the services cannot store."""

import pytest
from pydantic import BaseModel, ValidationError

from src.libs.schemas.document import CreateUploadRequest
from src.libs.schemas.tenant import CreateTenantRequest, UpdateTenantRequest
from src.libs.schemas.user import RegisterRequest, UpdateUserRequest

PASSWORD = "correct horse battery"
REQUESTS = [
    (CreateUploadRequest, {"filename": "report.pdf"}),
    (CreateTenantRequest, {"organisation": "ACME"}),
    (UpdateTenantRequest, {"organisation": "ACME"}),
    (
        RegisterRequest,
        {"username": "ada", "email": "ada@example.com", "password": PASSWORD},
    ),
    (UpdateUserRequest, {"username": "ada", "email": "ada@example.com"}),
]
IDS = [model.__name__ for model, _ in REQUESTS]


class TestStrictRequests:
    """Every request body accepts its own fields only."""

    @pytest.mark.parametrize(("model", "body"), REQUESTS, ids=IDS)
    def test_valid_body_is_accepted(self, model: type[BaseModel], body: dict):
        """
        GIVEN a body with only valid fields
        WHEN it is validated
        THEN it is accepted
        """
        model.model_validate(body)

    @pytest.mark.parametrize(("model", "body"), REQUESTS, ids=IDS)
    def test_unknown_field_is_rejected(self, model: type[BaseModel], body: dict):
        """
        GIVEN a body with an extra field (for example a client that tries to set
            its own roles)
        WHEN it is validated
        THEN ValidationError is raised instead of ignoring the field
        """
        with pytest.raises(ValidationError, match="extra_forbidden"):
            model.model_validate(body | {"roles": ["admin"]})


class TestText:
    """Names are trimmed, at most 255 characters and free of control characters."""

    @pytest.mark.parametrize(
        "value",
        ["", "   ", "a" * 256, "AC\x00ME", "AC\nME", "\x1b[31mACME"],
        ids=["empty", "blank", "too-long", "nul", "newline", "escape-sequence"],
    )
    def test_invalid_text_is_rejected(self, value: str):
        """
        GIVEN a name that is blank, longer than the column, or has control
            characters (Postgres rejects NUL; others break logs and headers)
        WHEN it is validated
        THEN ValidationError is raised
        """
        with pytest.raises(ValidationError):
            CreateTenantRequest(organisation=value)

    @pytest.mark.parametrize(
        ("value", "stored"),
        [
            ("  ACME  ", "ACME"),
            ("Ünïcode GmbH ✓", "Ünïcode GmbH ✓"),
            ("a" * 255, "a" * 255),
        ],
        ids=["trimmed", "unicode", "max-length"],
    )
    def test_valid_text_is_accepted(self, value: str, stored: str):
        """
        GIVEN a name with surrounding spaces, non-ASCII letters or 255 characters
        WHEN it is validated
        THEN it is accepted (trimmed)
        """
        assert CreateTenantRequest(organisation=value).organisation == stored


class TestEmail:
    """Email addresses are validated and stored in lower case."""

    def test_email_is_lower_cased(self):
        """
        GIVEN an email address in mixed case
        WHEN it is validated
        THEN it is stored in lower case, so login can compare it exactly
        """
        body = UpdateUserRequest(username="ada", email="Ada@Example.COM")

        assert body.email == "ada@example.com"

    @pytest.mark.parametrize(
        "email",
        ["ada", "ada@", "@example.com", "ada@example", f"{'a' * 250}@example.com"],
        ids=["no-at", "no-domain", "no-local-part", "no-tld", "too-long"],
    )
    def test_invalid_email_is_rejected(self, email: str):
        """
        GIVEN a string that is not a valid email address
        WHEN it is validated
        THEN ValidationError is raised
        """
        with pytest.raises(ValidationError):
            UpdateUserRequest(username="ada", email=email)
