#!/bin/sh
set -eu

# Pull configuration from environment variables
DB_HOST="${POSTGRES_SEEDS}"
DB_PORT="${DB_PORT:-5432}"

echo "Starting PostgreSQL schema setup..."
echo "Waiting for PostgreSQL port to be available at ${DB_HOST}:${DB_PORT}..."
# Add '-w 5' timeout parameter to prevent netcat from hanging indefinitely
until nc -z -w 5 "${DB_HOST}" "${DB_PORT}"; do
    echo "PostgreSQL port is not available yet. Retrying..."
    sleep 1
done

echo "PostgreSQL port is ready. Commencing schema initialization..."

# 1. Initialize and update Core Persistence Database
temporal-sql-tool --plugin postgres12 --endpoint "${DB_HOST}" --port "${DB_PORT}" --user "${TEMPORAL_POSTGRES_USER}" --password "${TEMPORAL_POSTGRES_PASSWORD}" --database "${TEMPORAL_POSTGRES_DB}" setup-schema -v 0.0
temporal-sql-tool --plugin postgres12 --endpoint "${DB_HOST}" --port "${DB_PORT}" --user "${TEMPORAL_POSTGRES_USER}" --password "${TEMPORAL_POSTGRES_PASSWORD}" --database "${TEMPORAL_POSTGRES_DB}" update-schema -d /etc/temporal/schema/postgresql/v12/temporal/versioned

# 2. Initialize and update Advanced Visibility Database
temporal-sql-tool --plugin postgres12 --endpoint "${DB_HOST}" --port "${DB_PORT}" --user "${TEMPORAL_POSTGRES_USER}" --password "${TEMPORAL_POSTGRES_PASSWORD}" --database "${TEMPORAL_POSTGRES_VISIBILITY_DB}" setup-schema -v 0.0
temporal-sql-tool --plugin postgres12 --endpoint "${DB_HOST}" --port "${DB_PORT}" --user "${TEMPORAL_POSTGRES_USER}" --password "${TEMPORAL_POSTGRES_PASSWORD}" --database "${TEMPORAL_POSTGRES_VISIBILITY_DB}" update-schema -d /etc/temporal/schema/postgresql/v12/visibility/versioned

echo "Temporal database schemas initialized successfully!"
