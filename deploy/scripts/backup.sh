#!/usr/bin/env sh
# ---------------------------------------------------------------------------
# CapitalOS database backup.
#
# Produces a compressed (and optionally AES-256 encrypted) logical dump of the
# Postgres database using pg_dump, then prunes old backups on a
# grandfather-father-son schedule (7 daily / 4 weekly / 6 monthly).
#
# Intended for later production use — it is NOT wired into the core build. Run
# it manually (`make backup`) or from the `backup` compose profile / cron.
#
# Requirements: docker compose (for pg_dump inside the postgres service),
# gzip, and — if encryption is enabled — openssl.
#
# Environment (usually from .env):
#   POSTGRES_DB, POSTGRES_USER            database + role to dump
#   BACKUP_ENCRYPTION_PASSPHRASE          if set, output is encrypted (openssl)
#   BACKUP_DIR                            output dir (default: ./backups)
#   COMPOSE_FILE                          compose file (default: docker-compose.yml)
#   PG_SERVICE                            compose service name (default: postgres)
# ---------------------------------------------------------------------------
set -eu
# `pipefail` is not in POSIX sh but is supported by bash/dash-with-pipefail;
# enable it when available so a failing pg_dump in a pipe is not masked by gzip.
# shellcheck disable=SC3040
(set -o pipefail 2>/dev/null) && set -o pipefail

# ------------------------------------------------------------------- config
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)

BACKUP_DIR=${BACKUP_DIR:-"$REPO_ROOT/backups"}
COMPOSE_FILE=${COMPOSE_FILE:-"$REPO_ROOT/docker-compose.yml"}
PG_SERVICE=${PG_SERVICE:-postgres}
POSTGRES_DB=${POSTGRES_DB:-capitalos}
POSTGRES_USER=${POSTGRES_USER:-capitalos}

# Load .env if present so this script works when invoked directly (not via make).
if [ -f "$REPO_ROOT/.env" ]; then
    # shellcheck disable=SC1091
    set -a; . "$REPO_ROOT/.env"; set +a
fi
# Dedicated backup config (DB target, encryption passphrase, rclone destination).
# Keep this file OUT of version control — see deploy/backup.env.example.
if [ -f "$REPO_ROOT/deploy/backup.env" ]; then
    # shellcheck disable=SC1091
    set -a; . "$REPO_ROOT/deploy/backup.env"; set +a
fi

# Off-site upload destination (e.g. "gdrive:CapitalOS" for rclone Google Drive).
RCLONE_DEST=${RCLONE_DEST:-}
RCLONE_RETENTION_DAYS=${RCLONE_RETENTION_DAYS:-90}

# Uploading finance data off-site without encryption would leak it to the
# storage provider — refuse to do that.
if [ -n "$RCLONE_DEST" ] && [ -z "${BACKUP_ENCRYPTION_PASSPHRASE:-}" ]; then
    printf '[backup] ERROR: RCLONE_DEST is set but BACKUP_ENCRYPTION_PASSPHRASE is not.\n' >&2
    printf '[backup] Refusing to upload an unencrypted backup off-site.\n' >&2
    exit 1
fi

TIMESTAMP=$(date -u +"%Y%m%dT%H%M%SZ")
mkdir -p "$BACKUP_DIR"

BASENAME="capitalos-${POSTGRES_DB}-${TIMESTAMP}.sql.gz"
OUTFILE="$BACKUP_DIR/$BASENAME"

log() { printf '[backup] %s\n' "$1" >&2; }

# ---------------------------------------------------------------- dump + gzip
log "Dumping database '$POSTGRES_DB' via compose service '$PG_SERVICE'..."

# --clean --if-exists makes the dump safely restorable over an existing schema.
DUMP_CMD="pg_dump --clean --if-exists --no-owner --no-privileges -U \"$POSTGRES_USER\" \"$POSTGRES_DB\""

if [ -n "${BACKUP_ENCRYPTION_PASSPHRASE:-}" ]; then
    OUTFILE="${OUTFILE}.enc"
    log "Encryption enabled -> $OUTFILE"
    docker compose -f "$COMPOSE_FILE" exec -T "$PG_SERVICE" sh -c "$DUMP_CMD" \
        | gzip -9 \
        | openssl enc -aes-256-cbc -salt -pbkdf2 \
            -pass env:BACKUP_ENCRYPTION_PASSPHRASE \
            -out "$OUTFILE"
else
    log "Encryption DISABLED (BACKUP_ENCRYPTION_PASSPHRASE not set) -> $OUTFILE"
    docker compose -f "$COMPOSE_FILE" exec -T "$PG_SERVICE" sh -c "$DUMP_CMD" \
        | gzip -9 > "$OUTFILE"
fi

# Sanity: refuse to keep a suspiciously tiny (likely failed) dump.
SIZE=$(wc -c < "$OUTFILE" | tr -d ' ')
if [ "$SIZE" -lt 100 ]; then
    log "ERROR: backup file is only ${SIZE} bytes; removing and failing."
    rm -f "$OUTFILE"
    exit 1
fi
log "Backup complete: $OUTFILE (${SIZE} bytes)"

# --------------------------------------------------------- off-site upload
# Copy the encrypted dump to a remote (Google Drive via rclone) and prune old
# remote copies by age. Google only ever sees the AES-256 ciphertext.
if [ -n "$RCLONE_DEST" ]; then
    if ! command -v rclone >/dev/null 2>&1; then
        log "ERROR: RCLONE_DEST set but 'rclone' is not installed."
        exit 1
    fi
    log "Uploading to $RCLONE_DEST ..."
    rclone copy "$OUTFILE" "$RCLONE_DEST" --no-traverse
    log "Uploaded $BASENAME to $RCLONE_DEST"
    log "Pruning remote backups older than ${RCLONE_RETENTION_DAYS}d ..."
    rclone delete "$RCLONE_DEST" --min-age "${RCLONE_RETENTION_DAYS}d" \
        --include "capitalos-*" 2>/dev/null || true
fi

# ------------------------------------------------------------------- pruning
# Retention: keep the 7 newest daily, 4 weekly (one per ISO week), 6 monthly
# (one per calendar month). Everything else is deleted. Files are matched by
# their UTC timestamp embedded in the filename.
prune() {
    keep_list=$(mktemp)
    trap 'rm -f "$keep_list"' EXIT

    # All backups, newest first.
    all=$(ls -1t "$BACKUP_DIR"/capitalos-*.sql.gz "$BACKUP_DIR"/capitalos-*.sql.gz.enc 2>/dev/null || true)
    [ -z "$all" ] && { log "Nothing to prune."; return 0; }

    # 7 most recent = daily retention.
    printf '%s\n' "$all" | head -n 7 >> "$keep_list"

    # Weekly: newest file per ISO year-week (up to 4).
    seen_weeks=""; weekly_count=0
    for f in $all; do
        ts=$(printf '%s' "$f" | sed -n 's/.*-\([0-9]\{8\}T[0-9]\{6\}Z\)\.sql\.gz.*/\1/p')
        [ -z "$ts" ] && continue
        ymd=$(printf '%s' "$ts" | cut -c1-8)
        week=$(_iso_week "$ymd")
        case " $seen_weeks " in *" $week "*) continue ;; esac
        seen_weeks="$seen_weeks $week"
        echo "$f" >> "$keep_list"
        weekly_count=$((weekly_count + 1))
        [ "$weekly_count" -ge 4 ] && break
    done

    # Monthly: newest file per calendar month (up to 6).
    seen_months=""; monthly_count=0
    for f in $all; do
        ts=$(printf '%s' "$f" | sed -n 's/.*-\([0-9]\{8\}T[0-9]\{6\}Z\)\.sql\.gz.*/\1/p')
        [ -z "$ts" ] && continue
        month=$(printf '%s' "$ts" | cut -c1-6)
        case " $seen_months " in *" $month "*) continue ;; esac
        seen_months="$seen_months $month"
        echo "$f" >> "$keep_list"
        monthly_count=$((monthly_count + 1))
        [ "$monthly_count" -ge 6 ] && break
    done

    # Delete anything not on the keep list.
    for f in $all; do
        if ! grep -qxF "$f" "$keep_list"; then
            log "Pruning old backup: $f"
            rm -f "$f"
        fi
    done
}

# ISO-week helper that works on both GNU (Linux) and BSD (macOS) date.
_iso_week() {
    ymd=$1
    if date -u -d "$ymd" +%G%V >/dev/null 2>&1; then
        date -u -d "$ymd" +%G%V           # GNU date
    else
        date -u -j -f "%Y%m%d" "$ymd" +%G%V  # BSD date
    fi
}

log "Applying retention policy (7 daily / 4 weekly / 6 monthly)..."
prune
log "Done."
