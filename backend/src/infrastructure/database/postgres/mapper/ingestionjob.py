from src.domain.ingestions.entities import IngestionJobEntity
from src.infrastructure.database.postgres.models.ingestion import IngestionJob


class IngestionJobMapper:
    @staticmethod
    def to_model(entity: IngestionJobEntity) -> IngestionJob:
        return IngestionJob(
            job_id=entity.job_id,
            document_id=entity.document_id,
            workflow_id=entity.workflow_id,
            workflow_run_id=entity.workflow_run_id,
            current_stage=entity.current_stage,
            status=entity.status,
            attempt_count=entity.attempt_count,
            error_message=entity.error_message,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            started_at=entity.started_at,
            finished_at=entity.finished_at,
        )

    @staticmethod
    def to_entity(model: IngestionJob) -> IngestionJobEntity:
        return IngestionJobEntity(
            job_id=model.job_id,
            document_id=model.document_id,
            workflow_id=model.workflow_id,
            workflow_run_id=model.workflow_run_id,
            current_stage=model.current_stage,
            status=model.status,
            attempt_count=model.attempt_count,
            error_message=model.error_message,
            created_at=model.created_at,
            updated_at=model.updated_at,
            started_at=model.started_at,
            finished_at=model.finished_at,
        )
