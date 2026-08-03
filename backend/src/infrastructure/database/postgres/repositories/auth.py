from src.shared.core.logger import get_logger
from src.domain.auth.repository import AuthTokenRepository

logger = get_logger("api.infra.postgres.auth")


class PostgresAuthRepository(AuthTokenRepository): ...
