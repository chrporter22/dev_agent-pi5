#!/usr/bin/env bash
set -Eeuo pipefail

############################################
# OpenClaw LLM + VDB Bootstrap Installer
# Hardened + Deterministic + Reproducible
############################################

LLM_VOLUME="openclaw_llm_model"
MODEL_FILENAME="qwen2-1_5b-instruct-q4_k_m.gguf"

# ---- REQUIRED: Set these ----
MODEL_URL="https://YOUR_MODEL_DOWNLOAD_URL"
MODEL_SHA256="REPLACE_WITH_EXPECTED_SHA256_HASH"

############################################
# Logging Helpers
############################################

log() { echo -e "\033[1;32m[INFO]\033[0m $1"; }
warn() { echo -e "\033[1;33m[WARN]\033[0m $1"; }
error() { echo -e "\033[1;31m[ERROR]\033[0m $1"; exit 1; }

############################################
# 1️⃣ Validate Host Architecture
############################################

ARCH=$(uname -m)
if [[ "$ARCH" != "aarch64" ]]; then
    error "Unsupported architecture: $ARCH. Expected ARM64 (aarch64)."
fi
log "Architecture check passed (ARM64)."

############################################
# 2️⃣ Validate System Memory (>= 15GB)
############################################

TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
TOTAL_MEM_GB=$((TOTAL_MEM_KB / 1024 / 1024))

if [[ "$TOTAL_MEM_GB" -lt 15 ]]; then
    error "Insufficient memory detected: ${TOTAL_MEM_GB}GB. Raspberry Pi 5 16GB required."
fi
log "Memory check passed (${TOTAL_MEM_GB}GB detected)."

############################################
# 3️⃣ Validate Docker Environment
############################################

if ! command -v docker &> /dev/null; then
    error "Docker not installed."
fi

if ! docker info &> /dev/null; then
    error "Docker daemon not running."
fi

if ! docker compose version &> /dev/null; then
    error "Docker Compose plugin not available."
fi

log "Docker environment validated."

############################################
# 4️⃣ Ensure LLM Model Volume Exists
############################################

if ! docker volume inspect "$LLM_VOLUME" &> /dev/null; then
    log "Creating Docker volume: $LLM_VOLUME"
    docker volume create "$LLM_VOLUME" > /dev/null
fi

############################################
# 5️⃣ Check If Model Already Exists
############################################

MODEL_PRESENT=$(docker run --rm \
    -v "$LLM_VOLUME:/models" \
    busybox sh -c "test -f /models/$MODEL_FILENAME && echo yes || echo no")

if [[ "$MODEL_PRESENT" == "yes" ]]; then
    log "Model already present in volume."
else
    log "Model not found in volume. Downloading..."

    TMP_DIR=$(mktemp -d)
    trap 'rm -rf "$TMP_DIR"' EXIT

    cd "$TMP_DIR"

    if [[ -z "$MODEL_URL" || -z "$MODEL_SHA256" ]]; then
        error "MODEL_URL and MODEL_SHA256 must be set in script."
    fi

    wget -O "$MODEL_FILENAME" "$MODEL_URL"

    log "Verifying model integrity (SHA256)..."

    DOWNLOADED_HASH=$(sha256sum "$MODEL_FILENAME" | awk '{print $1}')

    if [[ "$DOWNLOADED_HASH" != "$MODEL_SHA256" ]]; then
        error "SHA256 verification failed!
Expected: $MODEL_SHA256
Actual:   $DOWNLOADED_HASH"
    fi

    log "SHA256 verification passed."

    log "Populating Docker volume..."

    docker run --rm \
        -v "$LLM_VOLUME:/models" \
        -v "$TMP_DIR:/tmp/model" \
        busybox cp "/tmp/model/$MODEL_FILENAME" "/models/"

    log "Model copied into Docker volume."
fi

############################################
# 6️⃣ Validate Model Integrity Inside Volume
############################################

VOLUME_HASH=$(docker run --rm \
    -v "$LLM_VOLUME:/models" \
    busybox sha256sum "/models/$MODEL_FILENAME" | awk '{print $1}')

if [[ "$VOLUME_HASH" != "$MODEL_SHA256" ]]; then
    error "Volume model hash mismatch. Possible corruption."
fi

log "Volume integrity verified."

############################################
# 7️⃣ Validate Compose File Exists
############################################

if [[ ! -f "docker-compose.yml" && ! -f "compose.yml" ]]; then
    error "docker-compose.yml not found in current directory."
fi

############################################
# 8️⃣ Bootstrap OpenClaw VDB (NVMe, embeddings, index)
############################################

log "Bootstrapping OpenClaw VDB..."
if [[ ! -f "./bootstrap_vdb.sh" ]]; then
    error "bootstrap_vdb.sh not found in root directory."
fi

./bootstrap_vdb.sh
log "VDB bootstrap complete."

############################################
# 9️⃣ Build LLM Image Deterministically
############################################

log "Building LLM container..."
docker compose build --no-cache openclaw-llm

############################################
# Start LLM Service
############################################

log "Starting OpenClaw LLM..."
docker compose up -d openclaw-llm

############################################
# Post-Launch Validation
############################################

sleep 5

RUNNING=$(docker inspect -f '{{.State.Running}}' openclaw-llm 2>/dev/null || echo "false")

if [[ "$RUNNING" != "true" ]]; then
    error "LLM container failed to start."
fi

log "OpenClaw LLM started successfully."

############################################
# Summary
############################################

echo ""
log "Bootstrap complete."
echo "------------------------------------------"
echo "Volume:        $LLM_VOLUME"
echo "Model file:    $MODEL_FILENAME"
echo "Architecture:  $ARCH"
echo "Memory:        ${TOTAL_MEM_GB}GB"
echo "Container:     openclaw-llm"
echo "------------------------------------------"
log "OpenClaw VDB ready at ./core/vdb/data"
