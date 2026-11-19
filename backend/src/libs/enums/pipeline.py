from enum import StrEnum


class PipelineKind(StrEnum):
    """The pipeline step that a pipeline_config row describes."""

    CHUNKING = "chunking"
    ENTITY_EXTRACTION = "entity_extraction"
    EMBEDDING = "embedding"
    COMMUNITY_DETECTION = "community_detection"
    COMMUNITY_REPORT = "community_report"
