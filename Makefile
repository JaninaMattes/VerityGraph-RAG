# Run every target from the repository root.
COMPOSE = docker compose -f docker/compose.yaml
BACKEND = cd backend &&

.PHONY: help install dev worker up down logs lint test test-integration test-e2e check create-admin

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
	@echo "  make test-integration - Tests against a real Postgres (TEST_DATABASE_URL)"
	@echo "  make test-e2e - Upload-to-chunks test with real services in Docker"
	@echo "  make create-admin ORG=.. ADMIN_USERNAME=.. ADMIN_EMAIL=.. - First tenant admin"
	@echo "  make check    - lint + test (the same checks as CI)"

install:
	$(BACKEND) uv sync --locked --extra ingestion

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

# Needs an empty, disposable database, for example:
#   TEST_DATABASE_URL=postgresql+asyncpg://postgres@localhost:5432/test make test-integration
# Add DOCLING_INTEGRATION=1 to also run real Docling on a PDF (downloads models).
test-integration:
	$(BACKEND) uv run pytest tests/integration

# Upload -> MinIO event -> Temporal workflow -> real Docling -> Postgres.
# Needs Docker; starts and removes its own Postgres and MinIO containers.
test-e2e:
	$(BACKEND) E2E=1 uv run pytest tests/e2e -v

# Create a tenant and its first admin. The password is prompted (hidden) or read
# from VERITYGRAPH_ADMIN_PASSWORD; it is never a command-line argument.
create-admin:
	$(BACKEND) uv run python -m src.cli create-admin \
		--organisation "$(ORG)" --username "$(ADMIN_USERNAME)" --email "$(ADMIN_EMAIL)"

check: lint test
