from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Tenant:
    """
    Domain representation of a new tenant object.

    This object is independent of FastAPI's UploadFile and can be created from
    uploads, local files, web crawlers, S3 downloads, etc.
    """

    organisation: str
