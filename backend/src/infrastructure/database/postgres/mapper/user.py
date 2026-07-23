from src.domain.users.entities import UserEntity
from src.infrastructure.database.postgres.models.user import User


class UserMapper:
    @staticmethod
    def to_model(entity: UserEntity) -> User:
        return User(
            user_id=entity.user_id,
            tenant_id=entity.tenant_id,
            username=entity.username,
            email=entity.email,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
            deleted_by=entity.deleted_by,
            status=entity.status,
            # DB handles created_at/updated_at on creation
        )

    @staticmethod
    def to_entity(model: User) -> UserEntity:
        return UserEntity(
            user_id=model.user_id,
            tenant_id=model.tenant_id,
            username=model.username,
            email=model.email,
            created_at=model.created_at,
            updated_at=model.updated_at,
            deleted_at=model.deleted_at,
            deleted_by=model.deleted_by,
            status=model.status,
        )
