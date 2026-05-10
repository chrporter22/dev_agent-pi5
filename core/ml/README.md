/core/ml
├── Dockerfile
├── requirements.txt
├── config.py
├── ml_worker.py
├── embedding_client.py
├── pca_engine.py
├── drift_detector.py
├── risk_engine.py
├── model_trainer.py
├── model_runtime.py
├── redis_store.py
├── models/
│   └── risk_model.tflite
└── data/

# OPENCLAW ML WORKER — PRODUCT REQUIREMENTS DOCUMENT (PRD)

Version: 1.0  
Service: openclaw-ml  
Scope: Internal ML + Analytics System  
Runtime: Docker Container (Python 3.11)  
Network: Internal-only (no exposed ports)

==================================================
1. PURPOSE
==================================================

The ML Worker is a background intelligence service responsible for transforming raw embeddings from the Vector Database into:

- dimensionality-reduced representations (PCA)
- system drift signals
- risk classification scores
- optional trained ML model predictions

It is NOT user-facing and does NOT handle requests directly.

Its role is to continuously analyze system state and write results into Redis for downstream consumers (Node API + Dashboard).

==================================================
2. DESIGN PRINCIPLES
==================================================

- Fully asynchronous batch processing
- Stateless compute (Redis is the state layer)
- No HTTP API exposure
- No direct user interaction
- Fail-safe operation (silent recovery)
- Internal-only network communication
- Deterministic outputs where possible

==================================================
3. SYSTEM INPUTS
==================================================

PRIMARY DATA SOURCE:

Vector Database (openclaw-vdb)

- Embeddings retrieved in batch form
- Expected format: numerical vectors (numpy-compatible)

OPTIONAL INPUTS:

- historical embeddings (for drift comparison)
- cached PCA snapshots from Redis (future extension)

==================================================
4. CORE PIPELINE
==================================================

The ML Worker executes the following pipeline in a loop:

--------------------------------------------------
STEP 1 — EMBEDDING INGESTION
--------------------------------------------------

- Fetch embeddings from VDB
- Validate shape and consistency
- Normalize missing or corrupted vectors
- Convert to numpy array

OUTPUT:
clean_embedding_matrix

--------------------------------------------------
STEP 2 — PCA COMPUTATION
--------------------------------------------------

Goal: reduce embedding dimensionality and extract structure.

PROCESS:
- standardization (mean=0, variance=1)
- covariance matrix computation
- eigen decomposition
- projection into 2D space (PC1, PC2)

OUTPUTS:
- pca:latest → projected embeddings
- pca:components → eigenvectors
- pca:variance → explained variance ratio

--------------------------------------------------
STEP 3 — DRIFT DETECTION
--------------------------------------------------

Goal: detect distribution shifts in embedding space.

METRICS:

1. Centroid Shift
   - distance between current mean vector and baseline

2. Variance Shift
   - deviation in feature variance distribution

3. Optional Rolling Window Drift
   - compares recent vs historical embedding windows

OUTPUT:
- drift:score (float 0–1+)
- drift:probability (normalized 0–1)

--------------------------------------------------
STEP 4 — RISK SCORING
--------------------------------------------------

Goal: classify system stability based on drift.

INPUT:
- drift_score

OUTPUT CLASSIFICATION:

- Low
- Medium
- High
- Critical

RULES:
- score < 0.25 → Low
- 0.25–0.5 → Medium
- 0.5–0.75 → High
- > 0.75 → Critical

--------------------------------------------------
STEP 5 — MODEL TRAINING (OPTIONAL PIPELINE)
--------------------------------------------------

Purpose:
Train lightweight predictive model on PCA features.

MODEL TYPE:
- Logistic Regression OR single-layer neural network

INPUT:
- PCA features (PC1, PC2)

OUTPUT:
- TensorFlow Lite model

EXPORT:
/opt/models/risk_model.tflite

--------------------------------------------------
STEP 6 — MODEL INFERENCE
--------------------------------------------------

Purpose:
Provide fast prediction layer using trained model.

PROCESS:
- load TFLite model
- run inference on PCA features
- compute prediction + confidence

OUTPUT:
- prediction class
- confidence score

--------------------------------------------------
5. OUTPUT SYSTEM (REDIS)
--------------------------------------------------

All ML outputs are stored in Redis as system-wide cache.

KEYS:

PCA:
- pca:latest
- pca:components
- pca:variance

DRIFT:
- drift:score
- drift:probability
- drift:classification

RISK:
- risk:latest

OPTIONAL:
- model:prediction
- model:confidence

==================================================
6. EXECUTION MODEL
==================================================

The ML worker runs as a continuous loop:

LOOP:
    fetch embeddings
    run PCA
    compute drift
    compute risk
    store results in Redis
    sleep (30s default)

No external triggers are required.

==================================================
7. DEPENDENCIES
==================================================

PYTHON LIBRARIES:

- numpy
- scipy
- scikit-learn
- tensorflow
- tflite-runtime
- redis
- requests
- joblib

SYSTEM DEPENDENCIES:

- access to openclaw-vdb (internal network)
- access to redis (internal network)

==================================================
8. DOCKER BEHAVIOR
==================================================

CONTAINER CONSTRAINTS:

- read-only filesystem
- /tmp mounted as tmpfs
- no public ports exposed
- internal network only
- no-new-privileges enabled
- dropped capabilities

RESOURCE LIMITS:

- memory: 2GB
- pids: 150

==================================================
9. FAILURE HANDLING
==================================================

FAILURE MODES:

1. VDB unavailable
   - skip iteration
   - retry next cycle

2. invalid embeddings
   - sanitize input
   - log error silently

3. PCA failure
   - skip computation
   - preserve last known state

4. Redis failure
   - terminate loop safely (container restart handles recovery)

NO USER-FACING ERRORS ARE GENERATED.

==================================================
10. PERFORMANCE DESIGN
==================================================

- batch processing (no per-request computation)
- numpy vectorized operations
- periodic execution (not event-driven)
- minimal model size (TFLite optimized)
- Redis as cache layer (no recomputation)

==================================================
11. SECURITY MODEL
==================================================

- internal-only service
- no API exposure
- no authentication layer needed (network isolation handles trust boundary)
- no external data ingestion except VDB + Redis

==================================================
12. SYSTEM ROLE IN ARCHITECTURE
==================================================

ML Worker is NOT part of request flow.

It operates in a parallel intelligence layer:

VDB → ML Worker → Redis → Node API → Dashboard

It does NOT:

- handle user requests
- process Telegram commands
- execute GitHub actions
- interact with worker/bot

==================================================
13. FINAL SUMMARY
==================================================

The ML Worker is a background analytics engine that continuously:

- compresses embeddings (PCA)
- detects system drift
- evaluates risk levels
- optionally trains lightweight models
- stores all outputs in Redis

It is designed for:

- stability monitoring
- latent space visualization
- anomaly detection
- future predictive intelligence

==================================================
END OF PRD
==================================================
