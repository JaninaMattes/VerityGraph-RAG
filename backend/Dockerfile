# syntax=docker/dockerfile:1
# Backend images. Build context: the repository root (see Dockerfile.dockerignore).
#   target "api"    (default): the API and the migration job. Small: no torch.
#   target "worker":           the ingestion worker with Docling (extra "ingestion").
FROM python:3.15-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /uvx /bin/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
RUN useradd --system --uid 10001 app

# Dependencies first: these layers are rebuilt only when the lock file changes.
COPY backend/pyproject.toml backend/uv.lock ./


FROM base AS worker
RUN uv sync --locked --no-dev --no-cache --extra ingestion
COPY backend/src ./src
# Docling downloads its layout models and the tokenizer here on the first file.
# Mount a volume on this path to keep them across restarts.
ENV HF_HOME=/app/.cache/huggingface
RUN mkdir -p "$HF_HOME" && chown -R app "$HF_HOME"
USER app
CMD ["python", "-m", "src.infrastructure.message_broker.kafka.worker"]


FROM base AS api
RUN uv sync --locked --no-dev --no-cache
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/src ./src
USER app
EXPOSE 8000
# PORT is set by hosting platforms such as Render; 8000 is the local default.
CMD ["sh", "-c", "exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
