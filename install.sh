#!/usr/bin/env bash
set -Eeuo pipefail

# -------------------------
# ENV CHECKS
# -------------------------
# This repo no longer ships a local LLM model. `openclaw-llm` is a thin
# Flask proxy to an external LiteLLM gateway (configured via env). Required
# gateway env vars must already be present in `.env` before this script runs.

log() { echo -e "\033[1;32m[INFO]\033[0m $1"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m $1"; }
error() { echo -e "\033[1;31m[ERROR]\033[0m $1"; exit 1; }

# -------------------------
# ARCH CHECK
# -------------------------
ARCH=$(uname -m)
[[ "$ARCH" == "aarch64" ]] || error "ARM64 required"

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
# GATEWAY CONFIG CHECK
# -------------------------
if [[ -f ".env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

[[ -n "${AI_GATEWAY_BASE_URL:-}" ]] || error "AI_GATEWAY_BASE_URL missing from .env"
[[ -n "${AI_GATEWAY_API_KEY:-}" ]]  || error "AI_GATEWAY_API_KEY missing from .env"
[[ -n "${AI_GATEWAY_MODEL:-}" ]]    || error "AI_GATEWAY_MODEL missing from .env"

log "AI gateway env OK"

# -------------------------
# VDB BOOTSTRAP (SAFE RUN)
# -------------------------
if [[ -f "./bootstrap_vdb.sh" ]]; then
    log "Bootstrapping VDB"
    ./bootstrap_vdb.sh
else
    warn "Skipping VDB bootstrap"
fi

# -------------------------
# BUILD LLM PROXY
# -------------------------
log "Building LLM proxy"
docker compose build openclaw-llm

# -------------------------
# START SYSTEM
# -------------------------
log "Starting LLM proxy"
docker compose up -d openclaw-llm

sleep 5

# -------------------------
# BASIC HEALTH CHECK
# -------------------------
RUNNING=$(docker inspect -f '{{.State.Running}}' openclaw-llm 2>/dev/null || echo "false")

[[ "$RUNNING" == "true" ]] || error "LLM proxy failed to start"

log "LLM proxy container running"

# OPTIONAL: API CHECK (if Flask is exposed internally)
if curl -s http://localhost:8080/health >/dev/null 2>&1; then
    log "LLM proxy API responsive"
else
    warn "LLM proxy API not reachable yet (may still be booting)"
fi

echo ""
log "Bootstrap complete"
echo "--------------------------------"
echo "LLM: openclaw-llm (proxy)"
echo "Gateway: ${AI_GATEWAY_BASE_URL}"
echo "Gateway model: ${AI_GATEWAY_MODEL}"
echo "RAM: ${TOTAL_MEM_GB}GB"
echo "Arch: $ARCH"
echo "--------------------------------"
