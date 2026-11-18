"""Request and response bodies of the /users endpoints."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.libs.enums.user import UserStatus
from src.libs.types import NonEmptyStr


class RegisterRequest(BaseModel):
    username: NonEmptyStr
    email: NonEmptyStr
    password_hash: str


class UpdateUserRequest(BaseModel):
    username: NonEmptyStr
    email: NonEmptyStr


class UserResponse(BaseModel):
    """Built from a UserEntity with UserResponse.model_validate(entity)."""

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    username: str
    email: str
    status: UserStatus
