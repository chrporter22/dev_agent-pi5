#!/usr/bin/env bash
set -Eeuo pipefail

LLM_VOLUME="openclaw_llm_model"
MODEL_FILENAME="qwen2-1_5b-instruct-q4_k_m.gguf"

MODEL_URL="https://YOUR_MODEL_DOWNLOAD_URL"
MODEL_SHA256="REPLACE_WITH_EXPECTED_SHA256_HASH"

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
# MODEL VOLUME (IDEMPOTENT)
# -------------------------
docker volume inspect "$LLM_VOLUME" >/dev/null 2>&1 || {
    log "Creating volume"
    docker volume create "$LLM_VOLUME" >/dev/null
}

# -------------------------
# MODEL CHECK
# -------------------------
MODEL_PRESENT=$(docker run --rm \
    -v "$LLM_VOLUME:/models" \
    busybox sh -c "test -f /models/$MODEL_FILENAME && echo yes || echo no")

if [[ "$MODEL_PRESENT" != "yes" ]]; then

    [[ -n "$MODEL_URL" && -n "$MODEL_SHA256" ]] || error "Model config missing"

    TMP_DIR=$(mktemp -d)
    trap 'rm -rf "$TMP_DIR"' EXIT

    log "Downloading model..."
    wget -O "$TMP_DIR/$MODEL_FILENAME" "$MODEL_URL"

    DOWNLOADED_HASH=$(sha256sum "$TMP_DIR/$MODEL_FILENAME" | awk '{print $1}')

    [[ "$DOWNLOADED_HASH" == "$MODEL_SHA256" ]] || error "SHA mismatch"

    docker run --rm \
        -v "$LLM_VOLUME:/models" \
        -v "$TMP_DIR:/tmp/model" \
        busybox cp "/tmp/model/$MODEL_FILENAME" "/models/"

    log "Model installed"
else
    log "Model already exists"
fi

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
# BUILD LLM
# -------------------------
log "Building LLM"
docker compose build openclaw-llm

# -------------------------
# START SYSTEM
# -------------------------
log "Starting LLM"
docker compose up -d openclaw-llm

sleep 5

# -------------------------
# BASIC HEALTH CHECK
# -------------------------
RUNNING=$(docker inspect -f '{{.State.Running}}' openclaw-llm 2>/dev/null || echo "false")

[[ "$RUNNING" == "true" ]] || error "LLM failed to start"

log "LLM container running"

# OPTIONAL: API CHECK (if Flask is exposed internally)
if curl -s http://localhost:8080/parse >/dev/null 2>&1; then
    log "LLM API responsive"
else
    warn "LLM API not reachable yet (may still be booting)"
fi

echo ""
log "Bootstrap complete"
echo "--------------------------------"
echo "LLM: openclaw-llm"
echo "Model: $MODEL_FILENAME"
echo "RAM: ${TOTAL_MEM_GB}GB"
echo "Arch: $ARCH"
echo "--------------------------------"
