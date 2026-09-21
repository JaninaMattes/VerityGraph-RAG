#!/bin/bash
set -e
set -u

function create_user_and_database() {
	# Input format expected: "dbname,dbuser"
	local database=$(echo "$1" | tr ',' ' ' | awk '{print $1}')
	local owner=$(echo "$1" | tr ',' ' ' | awk '{print $2}')
	local password="${TEMPORAL_POSTGRES_PASSWORD:-$owner}"
	
	echo "  Creating user '$owner' and database '$database'"
	
	# Execute user creation, then create DB
	psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOSQL
		DO \$\$
		BEGIN
			IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$owner') THEN
				CREATE USER $owner WITH ENCRYPTED PASSWORD '$password';
			ELSE
				ALTER USER $owner WITH ENCRYPTED PASSWORD '$password';
			END IF;
		END
		\$\$;

		CREATE DATABASE $database;
EOSQL

	# Assign ownership (Modern Postgres approach for safety)
	psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<-EOSQL
		ALTER DATABASE $database OWNER TO $owner;
		GRANT ALL PRIVILEGES ON DATABASE $database TO $owner;
EOSQL
}

if [ -n "${POSTGRES_MULTIPLE_DATABASES:-}" ]; then
	echo "Multiple database creation requested: $POSTGRES_MULTIPLE_DATABASES"
	# Split targets separated by colons (e.g., db1,user1:db2,user2)
	for db in $(echo "$POSTGRES_MULTIPLE_DATABASES" | tr ':' ' '); do
		create_user_and_database "$db"
	done
	echo "Multiple databases created successfully"
fi
