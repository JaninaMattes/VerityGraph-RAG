from uuid import UUID
from pydantic import BaseModel

from src.shared.enums import UserStatus

"""The schema module provides the building blocks for ..."""


class Response(BaseModel):
    user_id: UUID
    status: UserStatus


class CurrentUser(BaseModel):
    user_id: UUID
    username: str
    status: UserStatus
