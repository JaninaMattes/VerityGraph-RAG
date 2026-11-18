# Run every target from the repository root.
COMPOSE = docker compose -f docker/compose.yaml
BACKEND = cd backend &&

.PHONY: help install dev worker up down logs lint test check

help:
	@echo "VerityGraph commands:"
	@echo "  make install  - Install backend dependencies (uv)"
	@echo "  make dev      - Run the FastAPI server locally with reload"
	@echo "  make worker   - Run the Kafka/Temporal ingestion worker locally"
	@echo "  make up       - Start the Docker stack"
	@echo "  make down     - Stop the Docker stack"
	@echo "  make logs     - Follow the logs of the Docker stack"
	@echo "  make lint     - Ruff lint and format check"
	@echo "  make test     - Tests with coverage"
	@echo "  make check    - lint + test (the same checks as CI)"

install:
	$(BACKEND) uv sync --locked

dev:
	$(BACKEND) uv run fastapi dev src/main.py

worker:
	$(BACKEND) uv run python -m src.infrastructure.message_broker.kafka.worker

up:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

lint:
	$(BACKEND) uv run ruff check . && uv run ruff format --check .

test:
	$(BACKEND) uv run pytest tests --cov --cov-fail-under=95

check: lint test
