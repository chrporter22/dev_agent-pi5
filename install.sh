#!/usr/bin/env bash
set -Eeuo pipefail

# -------------------------
# ARCH CHECK
# -------------------------
ARCH=$(uname -m)
[[ "$ARCH" == "aarch64" ]] || error "ARM64 required"

log() { echo -e "\033[1;32m[INFO]\033[0m $1"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m $1"; }
error() { echo -e "\033[1;31m[ERROR]\033[0m $1"; exit 1; }

log "Architecture OK"

# -------------------------
# MEMORY CHECK
# -------------------------
TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_MEM_GB=$((TOTAL_MEM_KB / 1024 / 1024))

[[ "$TOTAL_MEM_GB" -ge 15 ]] || error "Need >=15GB RAM"

log "Memory OK (${TOTAL_MEM_GB}GB)"

# -------------------------
# DOCKER CHECK
# -------------------------
command -v docker >/dev/null || error "Docker missing"
docker info >/dev/null || error "Docker not running"
docker compose version >/dev/null || error "Docker Compose missing"

log "Docker OK"

# -------------------------
# ENV CHECK
# -------------------------
if [[ -f ".env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

[[ -n "${TELEGRAM_TOKEN:-}" ]]   || error "TELEGRAM_TOKEN missing from .env"
[[ -n "${REDIS_PASSWORD:-}" ]]   || error "REDIS_PASSWORD missing from .env"
[[ -n "${AI_GATEWAY_BASE_URL:-}" ]] || error "AI_GATEWAY_BASE_URL missing from .env"
[[ -n "${AI_GATEWAY_API_KEY:-}" ]]  || error "AI_GATEWAY_API_KEY missing from .env"

log "Environment OK"

# -------------------------
# BUILD ALL SERVICES
# -------------------------
log "Building all services"

docker compose -f docker-compose.prod.yml build

# -------------------------
# START SYSTEM
# -------------------------
log "Starting stack"

docker compose -f docker-compose.prod.yml up -d

sleep 5

# -------------------------
# BASIC HEALTH CHECK
# -------------------------
RUNNING=$(docker inspect -f '{{.State.Running}}' openclaw-bot 2>/dev/null || echo "false")

[[ "$RUNNING" == "true" ]] || warn "openclaw-bot may not have started"

RUNNING=$(docker inspect -f '{{.State.Running}}' openclaw-worker 2>/dev/null || echo "false")

[[ "$RUNNING" == "true" ]] || warn "openclaw-worker may not have started"

log "Stack is running"
echo ""
echo "--------------------------------"
echo "Services: openclaw-bot, openclaw-worker, redis, openclaw-ml, node-api, pca-backend"
echo "RAM: ${TOTAL_MEM_GB}GB"
echo "Arch: $ARCH"
echo "--------------------------------"