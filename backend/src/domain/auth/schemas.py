from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str


class LoginRequest(BaseModel):
    email: str
    hashed_password: str


class LoginResponse(BaseModel):
    status: str


class RegisterRequest(BaseModel):
    username: str
    email: str
    hashed_password: str


class RegisterResponse(BaseModel):
    status: str


class UserResponse(BaseModel):
    status: str
