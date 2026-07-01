#!/usr/bin/env bash
# Build and (re)deploy the CapitalOS app stack against the shared edge stack.
# Safe to re-run for updates. Run from anywhere:
#     bash deploy/scripts/deploy-capitalos.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
APP_COMPOSE="${REPO_ROOT}/deploy/stacks/capitalos/docker-compose.yml"
APP_ENV="${REPO_ROOT}/deploy/stacks/capitalos/.env"
EDGE_COMPOSE="${REPO_ROOT}/deploy/edge/docker-compose.yml"

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

[[ -f "$APP_ENV" ]] || { echo "Missing $APP_ENV (copy from .env.example)"; exit 1; }

# Preconditions: shared networks + edge stack running.
docker network inspect edge  >/dev/null 2>&1 || { echo "network 'edge' missing — run bootstrap.sh"; exit 1; }
docker network inspect dbnet >/dev/null 2>&1 || { echo "network 'dbnet' missing — run bootstrap.sh"; exit 1; }
if ! docker compose -f "$EDGE_COMPOSE" ps postgres | grep -q "Up\|running"; then
  echo "Edge stack (Caddy + Postgres) is not up. Start it: docker compose -f $EDGE_COMPOSE up -d"; exit 1
fi

log "Building images"
docker compose -f "$APP_COMPOSE" build

log "Starting CapitalOS (runs Alembic migrations on backend start)"
docker compose -f "$APP_COMPOSE" up -d

log "Waiting for backend health"
cid="$(docker compose -f "$APP_COMPOSE" ps -q backend)"
for i in $(seq 1 40); do
  status="$(docker inspect -f '{{.State.Health.Status}}' "$cid" 2>/dev/null || echo starting)"
  [[ "$status" == "healthy" ]] && { echo "backend healthy"; break; }
  sleep 3
done
[[ "${status:-}" == "healthy" ]] || { echo "Backend did not become healthy:"; docker compose -f "$APP_COMPOSE" logs --tail=50 backend; exit 1; }

log "Reloading Caddy (pick up any routing changes)"
docker compose -f "$EDGE_COMPOSE" exec -T caddy caddy reload --config /etc/caddy/Caddyfile 2>/dev/null || \
  docker compose -f "$EDGE_COMPOSE" restart caddy

log "Done. Status:"
docker compose -f "$APP_COMPOSE" ps
echo
echo "Visit https://${DOMAIN:-your-domain.example} and complete first-run owner setup."
