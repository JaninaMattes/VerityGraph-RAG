from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True, frozen=True)
class Tenant:
    """
    Domain representation of a new tenant object.

    This object is independent of FastAPI's UploadFile and can be created from
    uploads, local files, web crawlers, S3 downloads, etc.
    """

    organisation: str


@dataclass(slots=True, frozen=True)
class UpdateTenant:
    """
    Domain representation of an updated user object.
    """

    tenant_id: UUID
    organisation: str