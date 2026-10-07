from enum import StrEnum


class TenantStatus(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    SUSPENDED = "suspended"
