# Makefile

.PHONY: help install dev up down deploy test
help:
	@echo "GraphRAG Platform Commands:"
	@echo "  make install    - Install Python dependencies"
	@echo "  make dev        - Run FastAPI server locally"
	@echo "  make up         - Start local DBs (Docker)"
	@echo "  make down       - Stop local DBs"

install:
	pip install uv
	uv pip install -r services/api/requirements.txt

# Run Local Development Environment
up:
	docker-compose up -d
down:
	docker-compose down