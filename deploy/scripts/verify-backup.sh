#!/usr/bin/env sh
# ---------------------------------------------------------------------------
# CapitalOS backup verification.
#
# Proves a backup is actually restorable by restoring it into a THROWAWAY
# database and running a sanity count against a core table. The throwaway
# database is always dropped afterwards, even on failure.
#
# This catches the classic failure mode where backups run for months but were
# never actually restorable. Run it periodically (e.g. weekly cron) against the
# most recent backup.
#
# Usage:   deploy/scripts/verify-backup.sh <backup-file>
#
# Environment (usually from .env):
#   POSTGRES_DB, POSTGRES_USER            source db name + role
#   BACKUP_ENCRYPTION_PASSPHRASE          required for *.enc files
#   COMPOSE_FILE / PG_SERVICE             compose file / service name
#   VERIFY_TABLE                          table to count (default: users)
# ---------------------------------------------------------------------------
set -eu
# shellcheck disable=SC3040
(set -o pipefail 2>/dev/null) && set -o pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)

COMPOSE_FILE=${COMPOSE_FILE:-"$REPO_ROOT/docker-compose.yml"}
PG_SERVICE=${PG_SERVICE:-postgres}
POSTGRES_DB=${POSTGRES_DB:-capitalos}
POSTGRES_USER=${POSTGRES_USER:-capitalos}
VERIFY_TABLE=${VERIFY_TABLE:-users}

if [ -f "$REPO_ROOT/.env" ]; then
    # shellcheck disable=SC1091
    set -a; . "$REPO_ROOT/.env"; set +a
fi

log() { printf '[verify] %s\n' "$1" >&2; }
die() { printf '[verify] ERROR: %s\n' "$1" >&2; exit 1; }

BACKUP_FILE=${1:-}
[ -n "$BACKUP_FILE" ] || die "Usage: verify-backup.sh <backup-file>"
[ -f "$BACKUP_FILE" ] || die "Backup file not found: $BACKUP_FILE"

VERIFY_DB="capitalos_verify_$(date -u +%Y%m%d%H%M%S)"

psql_admin() {
    docker compose -f "$COMPOSE_FILE" exec -T "$PG_SERVICE" \
        psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres "$@"
}

cleanup() {
    log "Dropping throwaway database '$VERIFY_DB'..."
    psql_admin -c "DROP DATABASE IF EXISTS \"$VERIFY_DB\";" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

log "Creating throwaway database '$VERIFY_DB'..."
psql_admin -c "CREATE DATABASE \"$VERIFY_DB\";" >/dev/null

log "Restoring backup into '$VERIFY_DB' (this uses restore.sh with FORCE=1)..."
FORCE=1 TARGET_DB="$VERIFY_DB" "$SCRIPT_DIR/restore.sh" "$BACKUP_FILE"

log "Running sanity count on table '$VERIFY_TABLE'..."
COUNT=$(docker compose -f "$COMPOSE_FILE" exec -T "$PG_SERVICE" \
    psql -tA -U "$POSTGRES_USER" -d "$VERIFY_DB" \
    -c "SELECT COUNT(*) FROM \"$VERIFY_TABLE\";" | tr -d ' \r')

case "$COUNT" in
    ''|*[!0-9]*) die "Sanity query did not return a number (got: '$COUNT')." ;;
esac

log "OK: restored '$VERIFY_TABLE' has $COUNT row(s)."
if [ "$COUNT" -lt 1 ]; then
    log "WARNING: table '$VERIFY_TABLE' is empty — the backup may be from an uninitialised database."
fi
log "Backup verification succeeded."
