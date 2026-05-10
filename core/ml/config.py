# /core/ml/config.py

import os

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

VDB_HOST = os.getenv("VDB_HOST", "openclaw-vdb")
VDB_PORT = int(os.getenv("VDB_PORT", 8081))

MODEL_PATH = "/app/models/risk_model.tflite"

EMBEDDING_BATCH_SIZE = 128
PCA_COMPONENTS = 2
