"""The configuration of a pipeline step: what produced a chunk, mention or vector."""

import typing
import uuid

from sqlalchemy import UUID, Enum, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.postgres.base import Base
from src.infrastructure.database.postgres.models.mixins import CreatedAtMixin
from src.libs.enums.pipeline import PipelineKind


class PipelineConfig(CreatedAtMixin, Base):
    """One configuration of a pipeline step (parser, model, prompt, parameters).

    The id is derived from kind and config_hash, so the same configuration always
    maps to the same row. Rows are global (not per tenant) and immutable.
    """

    __tablename__ = "pipeline_config"

    config_id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True)
    # VARCHAR, not a native enum: new kinds need no ALTER TYPE.
    kind: Mapped[PipelineKind] = mapped_column(
        Enum(PipelineKind, native_enum=False, length=32)
    )
    component: Mapped[str] = mapped_column(String(255))
    component_version: Mapped[str] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(255))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    parameters: Mapped[dict[str, typing.Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    config_hash: Mapped[str] = mapped_column(String(64))

    __table_args__ = (
        UniqueConstraint("kind", "config_hash", name="uq_pipeline_config_hash"),
    )
