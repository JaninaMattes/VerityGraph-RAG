from datetime import datetime
from uuid import UUID


class DocumentChunkEntity:
    """
    Domain representation of a document chunk entity.

    This object lives inside the business layer and is independent of
    FastAPI, SQLAlchemy, or Pydantic.
    """

    def __init__(
        self,
        chunk_id: UUID,
        document_id: UUID,
        chunk_index: int,
        content: str,
        page_number: int | None,
        section_title: str | None,
        token_count: int,
        chunk_metadata: dict,
        source_locator: dict,
        created_at: datetime,
        updated_at: datetime,
    ) -> None:

        # Identity
        self.chunk_id = chunk_id
        self.document_id = document_id

        # Document chunk properties
        self.chunk_idx = chunk_index
        self.content = content
        self.page_number = page_number
        self.section_title = section_title
        self.token_count = token_count
        self.chunk_metadata = chunk_metadata
        self.source_locator = source_locator

        # Audit
        self.created_at = created_at
        self.updated_at = updated_at
