"""HTTP endpoint to log in: exchange an email and password for an access token."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from src.api.dependencies import (
    SettingsDep,
    get_auth_service,
    limit_login_attempts,
)
from src.domain.auth.service import AuthService
from src.infrastructure.security.tokens import create_access_token
from src.libs.schemas.auth import TokenResponse

router = APIRouter()


@router.post(
    "/auth/token",
    response_model=TokenResponse,
    # Runs before the endpoint, so a refused attempt costs no password check.
    dependencies=[Depends(limit_login_attempts)],
)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: SettingsDep,
) -> TokenResponse:
    """Return a bearer token for the user with this email (`username`) and password.

    Any wrong value returns the same 401, so the response does not reveal whether
    the email exists. Too many attempts from one address return 429.
    """
    principal = await service.authenticate(form.username, form.password)
    return TokenResponse(
        access_token=create_access_token(principal, settings),
        expires_in=settings.access_token_expire_minutes * 60,
    )
