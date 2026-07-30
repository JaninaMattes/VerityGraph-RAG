from uuid import UUID

from pydantic import BaseModel

from src.shared.enums import UserStatus

"""The schema module provides the building blocks for ..."""


class RegisterRequest(BaseModel):
    username: str
    email: str


class UpdateRequest(BaseModel):
    username: str
    email: str


class UserResponse(BaseModel):
    user_id: UUID
    status: UserStatus


class CurrentUser(BaseModel):
    user_id: UUID
    status: UserStatus
