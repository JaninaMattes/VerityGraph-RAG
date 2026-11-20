"""Request and response bodies of the /users endpoints."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from src.libs.enums.user import UserStatus
from src.libs.schemas.base import RequestModel
from src.libs.types import Email, NonEmptyStr


class RegisterRequest(RequestModel):
    username: NonEmptyStr
    email: Email
    # The upper limit bounds the hashing work that one request can cause.
    password: SecretStr = Field(min_length=12, max_length=128)


class UpdateUserRequest(RequestModel):
    username: NonEmptyStr
    email: Email


class UserResponse(BaseModel):
    """Built from a UserEntity with UserResponse.model_validate(entity)."""

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    username: str
    email: str
    status: UserStatus
