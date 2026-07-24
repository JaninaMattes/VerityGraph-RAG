from src.application.port.auth_repository import AuthTokenRepository
from src.core.logger import get_logger

logger = get_logger("api-backend.infra.postgres.auth")


class PostgresAuthRepository(AuthTokenRepository): ...
