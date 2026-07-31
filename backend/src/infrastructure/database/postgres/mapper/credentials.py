from src.domain.credentials.entities import CredentialsEntity
from src.infrastructure.database.postgres.models.credentials import UserCredentials


class CredentialsMapper:
    @staticmethod
    def to_model(entity: CredentialsEntity) -> UserCredentials:
        return UserCredentials(
            credentials_id=entity.credentials_id,
            user_id=entity.user_id,
            provider=entity.provider,
            password_hash=entity.password_hash,
            status=entity.status,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            password_changed_at=entity.password_changed_at,
            deleted_at=entity.deleted_at,
            deleted_by=entity.deleted_by,
        )

    @staticmethod
    def to_entity(model: UserCredentials) -> CredentialsEntity:
        return CredentialsEntity(
            credentials_id=model.credentials_id,
            user_id=model.user_id,
            provider=model.provider,
            password_hash=model.password_hash,
            status=model.status,
            created_at=model.created_at,
            updated_at=model.updated_at,
            password_changed_at=model.password_changed_at,
            deleted_at=model.deleted_at,
            deleted_by=model.deleted_by,
        )
