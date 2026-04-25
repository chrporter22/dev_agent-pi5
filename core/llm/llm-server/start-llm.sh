#!/bin/bash
set -e

MODEL_PATH="${MODEL_PATH:-/models/qwen2-1_5b-instruct-q4_k_m.gguf}"
CTX_SIZE=2048
THREADS=6

if [ ! -f "$MODEL_PATH" ]; then
  echo "Model not found at $MODEL_PATH"
  exit 1
fi

echo "Starting llama.cpp server..."

# ---------------------------
# START llama.cpp SERVER
# ---------------------------
./llama.cpp/server \
  --model "$MODEL_PATH" \
  --ctx-size $CTX_SIZE \
  --threads $THREADS \
  --mlock \
  --host 0.0.0.0 \
  --port 8081 &

LLAMA_PID=$!

echo "llama.cpp PID: $LLAMA_PID"

# ---------------------------
# SIGNAL HANDLING (CRITICAL FIX)
# ---------------------------
cleanup() {
  echo "Shutting down llama.cpp..."
  kill $LLAMA_PID || true
  exit 0
}

trap cleanup SIGTERM SIGINT

echo "Starting Flask LLM gateway..."

# ---------------------------
# START FLASK (BLOCKING)
# ---------------------------
python3 app.py &

FLASK_PID=$!

# Wait for either process to exit
wait $FLASK_PID
