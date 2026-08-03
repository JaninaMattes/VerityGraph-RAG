from uuid import UUID

from pydantic import BaseModel

from src.shared.enums.user import UserStatus

"""The schema module provides the building blocks for ..."""


class RegisterRequest(BaseModel):
    username: str
    email: str
    password_hash: str


class UpdateUserRequest(BaseModel):
    username: str
    email: str


class UserResponse(BaseModel):
    user_id: UUID
    username: str
    email: str
    status: UserStatus
