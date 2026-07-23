from src.domain.auth.repository import AuthTokenRepository
from src.utils.logger import get_logger

logger = get_logger("api-backend.infra.postgres.auth")


class PostgresAuthRepository(AuthTokenRepository): ...
