from src.core.logger import get_logger
from src.domain.auth.repository import AuthTokenRepository

logger = get_logger("api-backend.domain.auth.service")


class AuthService:
    """The service layer defines the authentication business logic
    that ineracts with the repository."""

    def __init__(self, repository: AuthTokenRepository) -> None:
        self.repository = repository

    async def register(self): ...

    async def login(self):
        ...
        # Find user
        # Verify password
        # Issue JWT
        # Store refresh token
        # Return tokens

    async def refresh(self): ...

    async def logout(self): ...

    async def change_password(self): ...

    async def forgot_password(self): ...

    async def reset_password(self): ...

    async def verify_email(self): ...
