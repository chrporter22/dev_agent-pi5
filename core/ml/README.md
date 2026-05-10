# TODO — NODE API 

==================================================
1. PURPOSE
==================================================

Add Redis-backed ML endpoints to pca-backend so React dashboard can fetch all PCA + ML data.

==================================================
2. BACKEND STRUCTURE CHANGE
==================================================

Create folder structure:

pca-backend/
├── routes/
│   └── ml.ts

==================================================
3. CREATE ML ROUTES FILE
==================================================

FILE:
pca-backend/routes/ml.ts

TASK:
Create Express router connected to Redis.

SETUP:
- import express
- import ioredis
- create router instance
- connect Redis using REDIS_URL env var

==================================================
4. ADD PCA SUMMARY ENDPOINT (CRITICAL)
==================================================

CREATE ROUTE:

GET /api/ml/pca/summary

FUNCTION:
Return all PCA + ML metrics in ONE response.

FETCH FROM REDIS:
- pca:latest
- pca:components
- pca:variance
- pca:eigenvalues
- pca:total_variance
- drift:score
- model:prediction
- model:confidence

RETURN JSON:

{
  projection,
  components,
  variance,
  eigenvalues,
  totalVariance,
  drift,
  risk,
  confidence
}

==================================================
5. ADD PCA HISTORY ENDPOINT
==================================================

GET /api/ml/pca/history

TASK:
- read list from Redis key: pca:history
- return parsed JSON array
- limit to last 100 entries

==================================================
6. ADD INDIVIDUAL PCA ENDPOINTS
==================================================

Create these endpoints:

GET /api/ml/pca/projection
GET /api/ml/pca/components
GET /api/ml/pca/variance
GET /api/ml/pca/eigenvalues

Each one:
- reads Redis key
- JSON.parse safely
- returns array

==================================================
7. ADD DRIFT ENDPOINT
==================================================

GET /api/ml/drift

FETCH:
- drift:score
- drift:classification

RETURN:
{
  drift,
  classification
}

==================================================
8. ADD RISK ENDPOINT
==================================================

GET /api/ml/risk

FETCH:
- model:prediction
- model:confidence

RETURN:
{
  prediction,
  confidence
}

==================================================
9. MOUNT ROUTES IN BACKEND ENTRYPOINT
==================================================

FILE:
pca-backend/index.ts

ADD IMPORT:

import mlRoutes from "./routes/ml"

MOUNT:

app.use("/api/ml", mlRoutes)

==================================================
10. FINAL SYSTEM FLOW
==================================================

ML Worker
   ↓
Redis
   ├── pca:latest
   ├── pca:history
   ├── pca:variance
   ├── pca:eigenvalues
   ├── pca:total_variance
   ├── drift:score
   ├── model:prediction
   └── model:confidence

   ↓

pca-backend (Node API)
   ↓
/api/ml/pca/summary
/api/ml/pca/history
/api/ml/pca/projection
/api/ml/pca/components
/api/ml/pca/variance
/api/ml/pca/eigenvalues
/api/ml/drift
/api/ml/risk

   ↓

React Dashboard

==================================================
11. CRITICAL FRONTEND ENDPOINT
==================================================

PRIMARY ENDPOINT:

GET /api/ml/pca/summary

USE CASE:
Single request for full dashboard rendering.

INCLUDES:
- PCA projection (for scatter plot)
- variance (for bar chart)
- drift (for anomaly UI)
- confidence (for UI glow)
- risk level (for status color)

==================================================
12. FRONTEND BENEFIT
==================================================

This enables:

- single-fetch dashboard updates
- smooth 5-second polling
- viridis-based PCA visualization
- real-time drift overlays
- animated latent space rendering
- reduced API latency and complexity

==================================================
5. NODE API ARCHITECTURE RULE (CRITICAL)
==================================================

CURRENT ISSUE:
Node API must remain read-only for ML outputs.

TASKS:

- Node API must ONLY read Redis
- Node API must NEVER trigger ML computations
- ML remains async batch system (~30s cycle)

DELIVERABLE:
- strict separation of concerns
- no synchronous ML calls
- cached-only API responses

==================================================
6. OPTIONAL SYSTEM STABILITY IMPROVEMENTS
==================================================

TASKS:

Add ML observability keys:

- ml:heartbeat
- ml:version
- ml:last_run

Example:
redis_client.set("ml:heartbeat", int(time.time()), ex=60)

BENEFIT:
- system monitoring
- crash detection
- lifecycle tracking

==================================================
7. FINAL PRIORITY SUMMARY
==================================================

CRITICAL FIXES (must implement):
- VDB embedding contract
- Redis key + Node API mapping
- empty embedding bootstrap handling
- /app/models directory safety

SHOULD FIX:
- Node API ML exposure layer
- embedding minimum threshold logic

OPTIONAL:
- ML heartbeat + version tracking


# End TODO LIST


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
STEP 5 — MODEL TRAINING PIPELINE
--------------------------------------------------
--------------------------------------------------

GOAL:
Train an optimized lightweight neural network model on PCA-transformed embeddings to predict system risk states.

This replaces classical logistic regression with a tunable Keras-based single-layer neural network.

The objective is to maximize predictive accuracy while maintaining extremely low inference cost for edge deployment (TensorFlow Lite).

--------------------------------------------------
MODEL TYPE
--------------------------------------------------

Primary Model:
- Keras Sequential Model
- Single hidden layer (minimal complexity design)
- Softmax output for multi-class classification

Example structure:

INPUT → Dense(hidden_units, activation) → OUTPUT(softmax)

Where:
- Input: PCA features (PC1, PC2, PC3, PC4, PC5)
- Output: risk class (Low / Medium / High / Critical)

--------------------------------------------------
HYPERPARAMETER SEARCH STRATEGY
--------------------------------------------------

To avoid static model selection, the system uses RANDOM SEARCH + HYPERPARAMETER TUNING.

Search space includes:

- hidden_units:
  [4, 8, 16, 32]

- activation:
  ["relu", "tanh"]

- learning_rate:
  [0.001, 0.0005, 0.0001]

- batch_size:
  [8, 16, 32]

- epochs:
  [10, 25, 50]

- optimizer:
  ["adam", "rmsprop"]

PROCESS:

1. Randomly sample configurations
2. Train candidate model
3. Evaluate on validation split
4. Select best-performing configuration based on:
   - validation accuracy
   - loss stability
   - generalization score

--------------------------------------------------
TRAINING PIPELINE
--------------------------------------------------

INPUT DATA:
- PCA feature matrix (PC1, PC2)
- labeled risk categories

STEPS:

1. Normalize PCA features
2. Split dataset:
   - 80% training
   - 20% validation

3. Run hyperparameter search loop:
   FOR each sampled config:
       build model
       train model
       evaluate metrics
       store score

4. Select best model
5. Retrain best model on full dataset

--------------------------------------------------
MODEL OUTPUT
--------------------------------------------------

Final trained model is exported as:

- TensorFlow SavedModel (intermediate)
- TensorFlow Lite (.tflite) for inference

--------------------------------------------------
MODEL METADATA STORAGE
--------------------------------------------------

After training, full metadata is persisted in Redis AND local artifact storage.

--------------------------------------------------
REDIS KEYS
--------------------------------------------------

model:latest

Contains:
- model version ID
- training timestamp
- selected hyperparameters
- accuracy score
- loss value
- feature normalization config

model:history

Contains:
- list of previous model versions
- performance comparisons
- drift alignment history

model:best_config

Contains:
- best hyperparameter set from random search

model:metrics

Contains:
- accuracy
- precision

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
