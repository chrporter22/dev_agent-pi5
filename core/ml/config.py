# /core/ml/config.py

import os


# --------------------------------------------------
# REDIS CONFIG
# --------------------------------------------------
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")


# --------------------------------------------------
# VDB CONFIG
# --------------------------------------------------
VDB_HOST = os.getenv("VDB_HOST", "openclaw-vdb")
VDB_PORT = int(os.getenv("VDB_PORT", 8081))


# --------------------------------------------------
# ML PIPELINE CONFIG
# --------------------------------------------------

# PCA SETTINGS
PCA_COMPONENTS = 5 

# EMBEDDING PROCESSING
EMBEDDING_BATCH_SIZE = 128
EMBEDDING_NORMALIZE = True

# DRIFT DETECTION
DRIFT_ROLLING_WINDOW = 50
DRIFT_THRESHOLD_LOW = 0.25
DRIFT_THRESHOLD_MEDIUM = 0.5
DRIFT_THRESHOLD_HIGH = 0.75

# RISK SCORING
RISK_CLASSES = ["Low", "Medium", "High", "Critical"]

# MODEL TRAINING (RANDOM SEARCH)
MODEL_SEARCH_TRIALS = 10

MODEL_HYPERPARAM_SPACE = {
    "hidden_units": [4, 8, 16, 32],
    "activation": ["relu", "tanh"],
    "learning_rate": [0.001, 0.0005, 0.0001],
    "batch_size": [8, 16, 32],
    "epochs": [10, 25, 50],
    "optimizer": ["adam", "rmsprop"]
}

# MODEL OUTPUT
MODEL_PATH = "/app/models/risk_model.tflite"
MODEL_KERAS_PATH = "/app/models/risk_model.keras"
MODEL_METADATA_PATH = "/app/models/model_metadata.json"

# INFERENCE SETTINGS
INFERENCE_BATCH_SIZE = 1

# ML LOOP INTERVAL (seconds)
ML_WORKER_SLEEP = 5 


# --------------------------------------------------
# FEATURE FLAGS
# --------------------------------------------------

ENABLE_MODEL_TRAINING = True
ENABLE_MODEL_INFERENCE = True
ENABLE_DRIFT_DETECTION = True
ENABLE_PCA = True


# --------------------------------------------------
# LOGGING
# --------------------------------------------------
ML_LOG_LEVEL = os.getenv("ML_LOG_LEVEL", "INFO")
