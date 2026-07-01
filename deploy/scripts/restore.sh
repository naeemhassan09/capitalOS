#!/usr/bin/env sh
# ---------------------------------------------------------------------------
# CapitalOS database restore.
#
# Restores a backup produced by backup.sh into the running Postgres database.
# Handles the three shapes backup.sh can emit:
#   *.sql.gz.enc   openssl AES-256 encrypted, gzip-compressed
#   *.sql.gz       gzip-compressed
#   *.sql          plain SQL
#
# THIS IS DESTRUCTIVE: the dump is taken with --clean --if-exists, so restoring
# drops and recreates existing objects. A confirmation prompt guards against
# accidents (skip with FORCE=1, e.g. for automated verification).
#
# Usage:   deploy/scripts/restore.sh <backup-file>
# Or:      make restore f=backups/capitalos-...sql.gz.enc
#
# Environment (usually from .env):
#   POSTGRES_DB, POSTGRES_USER            target database + role
#   BACKUP_ENCRYPTION_PASSPHRASE          required for *.enc files
#   TARGET_DB                             override target db (used by verify)
#   COMPOSE_FILE / PG_SERVICE             compose file / service name
#   FORCE=1                               skip the confirmation prompt
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

if [ -f "$REPO_ROOT/.env" ]; then
    # shellcheck disable=SC1091
    set -a; . "$REPO_ROOT/.env"; set +a
fi

TARGET_DB=${TARGET_DB:-$POSTGRES_DB}

log() { printf '[restore] %s\n' "$1" >&2; }
die() { printf '[restore] ERROR: %s\n' "$1" >&2; exit 1; }

BACKUP_FILE=${1:-}
[ -n "$BACKUP_FILE" ] || die "Usage: restore.sh <backup-file>"
[ -f "$BACKUP_FILE" ] || die "Backup file not found: $BACKUP_FILE"

# ------------------------------------------------------------ confirmation
if [ "${FORCE:-0}" != "1" ]; then
    printf '[restore] This will OVERWRITE database "%s". Type the db name to continue: ' "$TARGET_DB" >&2
    read -r answer
    [ "$answer" = "$TARGET_DB" ] || die "Confirmation did not match; aborting."
fi

# --------------------------------------------------- build the decode pipeline
# We stream: [decrypt] -> [gunzip] -> psql, so nothing large hits disk.
case "$BACKUP_FILE" in
    *.sql.gz.enc)
        [ -n "${BACKUP_ENCRYPTION_PASSPHRASE:-}" ] || \
            die "Encrypted backup but BACKUP_ENCRYPTION_PASSPHRASE is not set."
        log "Decrypting + decompressing $BACKUP_FILE ..."
        DECODE="openssl enc -d -aes-256-cbc -pbkdf2 -pass env:BACKUP_ENCRYPTION_PASSPHRASE -in \"$BACKUP_FILE\" | gzip -d"
        ;;
    *.sql.gz)
        log "Decompressing $BACKUP_FILE ..."
        DECODE="gzip -dc \"$BACKUP_FILE\""
        ;;
    *.sql)
        DECODE="cat \"$BACKUP_FILE\""
        ;;
    *)
        die "Unrecognised backup extension: $BACKUP_FILE"
        ;;
esac

log "Restoring into database '$TARGET_DB' (service '$PG_SERVICE')..."
# ON_ERROR_STOP=1 makes psql fail loudly on the first bad statement.
sh -c "$DECODE" | docker compose -f "$COMPOSE_FILE" exec -T "$PG_SERVICE" \
    psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$TARGET_DB"

log "Restore complete."
