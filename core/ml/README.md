# ML WORKER — PRODUCT REQUIREMENTS DOCUMENT (PRD)

Version: 2.0
Service: openclaw-ml
Scope: Internal ML + Analytics System
Runtime: Docker Container (Python 3.11)
Network: Internal-only (no exposed ports)
Status: numpy + rules (Keras + TFLite removed in Phase 4, 2026-10-31)

==================================================
1. PURPOSE
==================================================

The ML Worker is a background intelligence service responsible for
transforming raw embeddings from a data source into:

- dimensionality-reduced representations (PCA)
- system drift signals
- risk classification scores

It is NOT user-facing and does NOT handle requests directly.

Its role is to continuously analyze system state and write results into
Redis for downstream consumers (Node API + Dashboard).

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
- numpy-only math; no scipy, no scikit-learn in the hot path

==================================================
3. SYSTEM INPUTS
==================================================

PRIMARY DATA SOURCE:

A future embedding source (currently unwired). The vdb-based source
(`core/vdb/embeddings`) was removed in the 2026-10-24 simplify, and the
in-repo `embedding_client.py` was removed in Phase 4 (2026-10-31).

Until a source is wired, the worker loop runs but PCA/drift/risk are
skipped; `ml:heartbeat` and `ml:last_run` still tick.

EXPECTED FORMAT WHEN WIRED:

Numerical vectors (numpy-compatible), shape `(n_samples, n_features)`,
float32.

==================================================
4. CORE PIPELINE
==================================================

The ML Worker executes the following pipeline in a loop:

--------------------------------------------------
STEP 1 — EMBEDDING INGESTION
--------------------------------------------------

- Fetch embeddings from the configured source
- Validate shape and consistency
- Standardize (handled by `pca_engine`)
- Convert to numpy array

OUTPUT:
clean_embedding_matrix  (None while the source is unwired)

--------------------------------------------------
STEP 2 — PCA COMPUTATION
--------------------------------------------------

Goal: reduce embedding dimensionality and extract structure.

PROCESS:
- standardization (mean=0, variance=1; `std[std==0]=1.0` guards)
- covariance matrix via `np.cov`
- eigen decomposition via `np.linalg.eigh`
- projection into top-`k` components (default `k = 5`)

OUTPUTS (Redis keys, JSON-serialized where nested):
- pca:latest -> projected embeddings (list)
- pca:components -> eigenvectors
- pca:variance -> explained variance ratio
- pca:eigenvalues -> eigenvalues
- pca:mean -> mean vector
- pca:std -> std vector
- pca:total_variance -> scalar
- pca:history -> latest 100 projections (LIST)

--------------------------------------------------
STEP 3 — DRIFT DETECTION
--------------------------------------------------

Goal: detect distribution shifts in the embedding space.

METRICS:
1. Centroid Shift: `np.linalg.norm(np.mean(X, axis=0))`
2. Variance Shift: `np.mean(np.var(X, axis=0))`
3. Drift Score: `(centroid_shift + variance_shift) / 2`

OUTPUT (Redis keys):
- drift:score (float)
- drift:classification ("Stable" | "Moderate" | "High" | "Critical")

--------------------------------------------------
STEP 4 — RISK CLASSIFICATION (RULES-BASED)
--------------------------------------------------

Goal: classify system risk from the drift score.

THRESHOLDS (config.py):
- DRIFT_THRESHOLD_LOW = 0.25
- DRIFT_THRESHOLD_MEDIUM = 0.5
- DRIFT_THRESHOLD_HIGH = 0.75

CLASSES (RISK_CLASSES):
- "Low"       score < 0.25
- "Medium"    0.25 <= score < 0.5
- "High"      0.5 <= score < 0.75
- "Critical"  score >= 0.75

CONFIDENCE:
Deterministic rule margin. Normalized distance from the band edge,
mapped onto `[0.5, 1.0]`. Not a learned probability.

OUTPUT (Redis keys):
- model:prediction (label string)
- model:confidence (float)
- risk:latest (same label, kept for back-compat with prior dashboards)

--------------------------------------------------
STEP 5 — HEARTBEAT
--------------------------------------------------

Always-on liveness signals, written every cycle:

- ml:heartbeat -> current UNIX timestamp (seconds)
- ml:last_run  -> current UNIX timestamp (seconds)

==================================================
5. OUTPUT SYSTEM (REDIS)
==================================================

All ML outputs are stored in Redis. The `ml` user (ACL) owns the
following key patterns: `pca:*`, `drift:*`, `risk:*`, `model:*`, `ml:*`.

KEYS:

PCA:
- pca:latest
- pca:components
- pca:variance
- pca:eigenvalues
- pca:mean
- pca:std
- pca:total_variance
- pca:history (LIST)

DRIFT:
- drift:score
- drift:classification

RISK:
- risk:latest
- model:prediction
- model:confidence

HEARTBEAT:
- ml:heartbeat
- ml:last_run

==================================================
6. EXECUTION MODEL
==================================================

The ML worker runs as a continuous loop:

LOOP:
    fetch embeddings
    if no data:
        write heartbeat
        sleep (ML_WORKER_SLEEP seconds, default 5)
        continue
    run PCA
    compute drift
    classify risk (rules)
    write results to Redis
    write heartbeat
    sleep

No external triggers are required.

==================================================
7. DEPENDENCIES
==================================================

PYTHON LIBRARIES:

- numpy
- redis
- requests (used by future data source clients; not by the worker loop itself)

SYSTEM DEPENDENCIES:

- access to redis (internal network, `ml` user)
- access to the future data source (not yet wired)

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

1. Data source unavailable
   - skip iteration
   - write heartbeat, retry next cycle
2. Invalid embeddings
   - sanitize input
   - log error silently, continue
3. PCA failure
   - skip computation
   - preserve last known state in Redis
4. Redis failure
   - terminate loop safely (container restart handles recovery)

NO USER-FACING ERRORS ARE GENERATED.

==================================================
10. SECURITY MODEL
==================================================

- internal-only service
- no API exposure
- no authentication layer needed (network isolation handles trust boundary)
- Redis access scoped to the `ml` user (per-service ACL)
- no secrets in the worker; env only

==================================================
11. SYSTEM ROLE IN ARCHITECTURE
==================================================

ML Worker is NOT part of request flow.

It operates in a parallel intelligence layer:

data source (future) -> ML Worker -> Redis -> Node API -> Dashboard

It does NOT:

- handle user requests
- process Telegram commands
- execute GitHub actions
- interact with worker/bot

==================================================
12. FINAL SUMMARY
==================================================

The ML Worker is a background analytics engine that continuously:

- compresses embeddings (PCA)
- detects system drift
- evaluates risk levels (rules-based)
- stores all outputs in Redis

It is designed for:

- stability monitoring
- latent space visualization
- anomaly detection
- simple, deterministic, explainable risk
