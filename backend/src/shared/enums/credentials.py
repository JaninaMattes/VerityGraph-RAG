from enum import StrEnum


class CredentialStatus(StrEnum):
    CREATED = "created"
    VALID = "valid"
    REVOKED = "revoked"
