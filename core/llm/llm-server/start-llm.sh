#!/bin/bash
set -e

MODEL_PATH="/models/qwen2-1_5b-instruct-q4_k_m.gguf"
CTX_SIZE=2048
THREADS=6
PORT=8080

if [ ! -f "$MODEL_PATH" ]; then
  echo "Model not found at $MODEL_PATH"
  exit 1
fi

echo "Starting llama.cpp server..."

# Start llama.cpp HTTP server in background
./llama.cpp/server \
  --model "$MODEL_PATH" \
  --ctx-size $CTX_SIZE \
  --threads $THREADS \
  --mlock \
  --host 0.0.0.0 \
  --port 8081 &

LLAMA_PID=$!

echo "Starting Flask wrapper..."

# Start Flask wrapper (LLM gateway)
python3 app.py

# Cleanup
kill $LLAMA_PID
