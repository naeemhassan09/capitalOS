#!/usr/bin/env bash
# Create (idempotently) a dedicated database + role in the SHARED Postgres for a
# site. Prints the DATABASE_URL to paste into that site's .env.
#
#   bash deploy/scripts/provision-db.sh <dbname> [password]
#
# If no password is given, a strong one is generated and printed once.
set -euo pipefail

DBNAME="${1:?usage: provision-db.sh <dbname> [password]}"
PASSWORD="${2:-$(openssl rand -hex 24)}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
EDGE_COMPOSE="${REPO_ROOT}/deploy/edge/docker-compose.yml"

if ! [[ "$DBNAME" =~ ^[a-z_][a-z0-9_]*$ ]]; then
  echo "dbname must be lowercase letters/digits/underscore (got: $DBNAME)" >&2
  exit 1
fi

# Ensure the shared Postgres is up.
if ! docker compose -f "$EDGE_COMPOSE" ps postgres | grep -q "Up\|running"; then
  echo "Shared Postgres is not running. Start it first:" >&2
  echo "  docker compose -f $EDGE_COMPOSE up -d" >&2
  exit 1
fi

psql() { docker compose -f "$EDGE_COMPOSE" exec -T postgres psql -v ON_ERROR_STOP=1 -U "${POSTGRES_SUPERUSER:-capitaladmin}" -d postgres "$@"; }

# Create role if missing, then (re)set its password.
psql <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DBNAME}') THEN
    CREATE ROLE ${DBNAME} LOGIN PASSWORD '${PASSWORD}';
  ELSE
    ALTER ROLE ${DBNAME} WITH PASSWORD '${PASSWORD}';
  END IF;
END
\$\$;
SQL

# Create the database if missing (owned by the role).
if ! psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DBNAME}'" | grep -q 1; then
  psql -c "CREATE DATABASE ${DBNAME} OWNER ${DBNAME};"
fi
psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DBNAME} TO ${DBNAME};"

cat <<EOF

Provisioned database + role "${DBNAME}" on the shared Postgres.
Put this in the site's .env (DATABASE_URL):

  DATABASE_URL=postgresql+psycopg2://${DBNAME}:${PASSWORD}@shared-postgres:5432/${DBNAME}

Store the password somewhere safe — it is not shown again.
EOF
