from enum import StrEnum


class IngestionStage(StrEnum):
    DOWNLOAD = "download"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    GRAPH_BUILDING = "graph_building"
    EVALUATION = "evaluation"


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"