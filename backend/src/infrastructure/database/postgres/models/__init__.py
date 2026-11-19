"""Model registry: importing this package registers every table on Base.metadata."""

from .chunk import DocumentChunk, DocumentChunkSpan
from .credentials import UserCredentials
from .document import Document
from .embedding import Embedding
from .graph import (
    Community,
    CommunityMember,
    CommunityReport,
    Entity,
    EntityMention,
    EntityRelationship,
    RelationshipEvidence,
)
from .ingestionjob import IngestionJob
from .pipeline import PipelineConfig
from .tenant import Tenant
from .user import User

__all__ = [
    "Community",
    "CommunityMember",
    "CommunityReport",
    "Document",
    "DocumentChunk",
    "DocumentChunkSpan",
    "Embedding",
    "Entity",
    "EntityMention",
    "EntityRelationship",
    "IngestionJob",
    "PipelineConfig",
    "RelationshipEvidence",
    "Tenant",
    "User",
    "UserCredentials",
]
