from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password_hash: str


class LoginResponse(BaseModel):
    status: str


class RegisterRequest(BaseModel):
    username: str
    email: str
    password_hash: str


class RegisterResponse(BaseModel):
    status: str


class UserResponse(BaseModel):
    status: str
