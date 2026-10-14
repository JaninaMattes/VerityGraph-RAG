from enum import StrEnum


class IngestionStage(StrEnum):
    INITIALISING = "initialising"
    DOWNLOAD = "download"
    PARSING = "parsing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    VECTOR_BUILDING = "vector_building"
    GRAPH_BUILDING = "graph_building"
    EVALUATION = "evaluation"


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"