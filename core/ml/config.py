# /core/ml/config.py
# Module-level env reads + ML pipeline constants.
# Hand-written validation, no zod (per project rule).

import os

# --------------------------------------------------
# REDIS CONFIG (per-service ACL: user `ml`)
# --------------------------------------------------
REDIS_USER = os.getenv("REDIS_USER", "ml")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

# --------------------------------------------------
# ML PIPELINE CONFIG
# --------------------------------------------------

# PCA SETTINGS
PCA_COMPONENTS = 5

# DRIFT THRESHOLDS (used by ml_worker.classify_drift and risk_classifier)
DRIFT_THRESHOLD_LOW = 0.25
DRIFT_THRESHOLD_MEDIUM = 0.5
DRIFT_THRESHOLD_HIGH = 0.75

# RISK CLASS LABELS (0..3)
RISK_CLASSES = ["Low", "Medium", "High", "Critical"]

# ML LOOP INTERVAL (seconds)
ML_WORKER_SLEEP = int(os.getenv("ML_WORKER_SLEEP", "5"))

# --------------------------------------------------
# DATA SOURCE
# --------------------------------------------------
# synthetic: seeded deterministic stream; dashboard renders out of the box.
# none:      pipeline idle, only the heartbeat ticks (pre-2026-11-07 default).
# A future value (e.g. gateway) can be added without changing the loop.
ML_DATA_SOURCE = os.getenv("ML_DATA_SOURCE", "synthetic")

# Synthetic stream shape. PCA needs >= 2 samples and >= 2 features.
ML_SYNTHETIC_SAMPLES = int(os.getenv("ML_SYNTHETIC_SAMPLES", "64"))
ML_SYNTHETIC_DIM = int(os.getenv("ML_SYNTHETIC_DIM", "128"))

# --------------------------------------------------
# LOGGING
# --------------------------------------------------
ML_LOG_LEVEL = os.getenv("ML_LOG_LEVEL", "INFO")
