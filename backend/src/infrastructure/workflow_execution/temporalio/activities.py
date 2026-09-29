import asyncio
from typing import Any

from temporalio import activity


@activity.defn
async def say_hello(name: str) -> str:
    return f"Hello, {name}!"


@activity.defn
async def create_ingestion_job_activity(document_id: str) -> str:
    activity.logger.info(f"Creating ingestion job for document {document_id}")
    # TODO: job = await job_repo.create(document_id)
    # return str(job.id)
    return "mock-job-id-123"


@activity.defn
async def update_ingestion_job_activity(job_id: str, status: str) -> None:
    activity.logger.info("Updating ingestion job %s status to %s.", job_id, status)
    # TODO: Inject DocumentRepository here and call:
    # await doc_repo.update_status(uuid.UUID(document_id), status)
    await asyncio.sleep(1)  # Simulate DB call


@activity.defn
async def update_document_activity(document_id: str, status: str) -> None:
    activity.logger.info("Updating document %s status to %s.", document_id, status)
    # TODO: Inject DocumentRepository here and call:
    # await doc_repo.update_status(uuid.UUID(document_id), status)
    await asyncio.sleep(1)  # Simulate DB call


@activity.defn
async def process_document_activity(payload: dict[str, Any]) -> None:
    activity.logger.info(
        f"Processing document: {payload['document_id']} from {payload['bucket']}"
    )
    # TODO: Heavy AI/ML work, MinIO download, chunking, embedding
    await asyncio.sleep(5)  # Simulate heavy processing
