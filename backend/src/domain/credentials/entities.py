from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from src.shared.enums import CredentialStatus


class CredentialsEntity:
    """
    Domain representation of provided user credentials.

    This object lives inside the business layer and is independent of
    FastAPI, SQLAlchemy, or Pydantic.
    """

    def __init__(
        self,
        *,
        credentials_id: UUID,
        user_id: UUID,
        provider: str | None = None,
        password_hash: str,
        status: CredentialStatus,
        created_at: datetime,
        updated_at: datetime,
        password_changed_at: datetime | None = None,
        deleted_at: datetime | None = None,
        deleted_by: UUID | None = None,
    ):
        self.credentials_id = credentials_id
        self.user_id = user_id
        self.provider = provider
        self.password_hash = password_hash
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at
        self.password_changed_at = password_changed_at
        self.deleted_at = deleted_at
        self.deleted_by = deleted_by

    def mark_updated(self) -> None:
        self.updated_at = datetime.now(UTC)

    def mark_revoked(self) -> None:
        self.status = CredentialStatus.REVOKED

    def mark_valid(self) -> None:
        self.status = CredentialStatus.VALID

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CredentialsEntity):
            return NotImplemented
        return self.credentials_id == other.credentials_id

    def __hash__(self) -> int:
        return hash(self.credentials_id)

    def __repr__(self) -> str:
        return f"CredentialsEntity(document_id={self.credentials_id!r}, provider={self.provider!r})"
