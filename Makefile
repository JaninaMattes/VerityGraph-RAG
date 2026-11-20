# Run every target from the repository root.
COMPOSE = docker compose -f docker/compose.yaml
# The cloud VM: MinIO behind Caddy, Kafka, Temporal and the worker. The API runs on
# Render and Postgres on Neon, so neither starts here (see docs/deployment.md).
COMPOSE_VM = $(COMPOSE) -f docker/compose.vm.yaml
VM_SERVICES = caddy minio minio-init-buckets kafka-kraft kafka-init-topics \
	postgresql temporal-admin-tools temporal temporal-create-namespace kafka-consumer
BACKEND = cd backend &&

# The first tenant admin (git-ignored; see docker/admin.env.example). The values
# also serve as defaults for `make create-admin`.
-include docker/admin.env
export VERITYGRAPH_ADMIN_PASSWORD
ORG ?= $(ADMIN_ORGANISATION)

.PHONY: help install dev worker up down logs lint test test-integration test-e2e check create-admin seed-demo admin-init up-vm

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
	@echo "  make seed-demo - Demo tenant with an admin and a member (development only)"
	@echo "  make admin-init - First admin in the stack from docker/admin.env (also run by up)"
	@echo "  make up-vm    - On the cloud VM: migrate Neon, start MinIO/Kafka/Temporal/worker"
	@echo "  make check    - lint + test (the same checks as CI)"

install:
	$(BACKEND) uv sync --locked --extra ingestion

dev:
	$(BACKEND) uv run fastapi dev src/main.py

worker:
	$(BACKEND) uv run python -m src.infrastructure.message_broker.kafka.worker

up:
	$(COMPOSE) up --build -d
	@if [ -f docker/admin.env ]; then $(MAKE) --no-print-directory admin-init; \
	else echo "No docker/admin.env: no admin created (see docker/admin.env.example)."; fi

# Create the first admin in the stack from docker/admin.env. Only this container
# receives the admin values. Without a password in the file, it prompts for one.
ADMIN_INIT = run --rm -e ADMIN_ORGANISATION="$(ADMIN_ORGANISATION)" \
	-e ADMIN_USERNAME="$(ADMIN_USERNAME)" -e ADMIN_EMAIL="$(ADMIN_EMAIL)" \
	-e VERITYGRAPH_ADMIN_PASSWORD

admin-init:
	$(COMPOSE) $(ADMIN_INIT) admin-init

# On the VM: migrate the Neon database, start the VM services, create the admin.
# --no-deps: the migration and the admin need Neon, not the local Postgres.
up-vm:
	$(COMPOSE_VM) build migrate kafka-consumer
	$(COMPOSE_VM) run --rm --no-deps migrate
	$(COMPOSE_VM) up -d $(VM_SERVICES)
	@if [ -f docker/admin.env ]; then $(COMPOSE_VM) $(ADMIN_INIT) --no-deps admin-init; \
	else echo "No docker/admin.env: no admin created (see docker/admin.env.example)."; fi

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

# Create a demo tenant with an admin and a member. Their random passwords are
# printed once. Refused when ENVIRONMENT=production.
seed-demo:
	$(BACKEND) uv run python -m src.cli seed-demo

check: lint test
