from src.domain.credentials.repository import CredentialsRepository
from src.infrastructure.storage.provider import StorageProvider


class CredentialService:
    """
    The service layer defines the authentication business logic
    that ineracts with the repository.
    """

    def __init__(
        self,
        repository: CredentialsRepository,
        storage: StorageProvider,
    ) -> None:
        self.repository = repository
        self.storage = storage