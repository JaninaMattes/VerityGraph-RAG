from enum import StrEnum


class UserStatus(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    DISABLED = "disabled"


class UserRole(StrEnum):
    ADMIN = "admin"
    USER = "user"
