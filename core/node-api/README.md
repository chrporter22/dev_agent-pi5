````markdown
# NODE API PRD

---

# 1. PURPOSE

Add Redis-backed ML endpoints to the backend so the React dashboard can fetch all PCA, drift, and ML inference data from a single API layer.

The Node API acts as a **read-only ML exposure layer** between Redis and the frontend.

---

# 2. SYSTEM ARCHITECTURE

```text
Embedding Pipeline
        ↓
ML Worker
        ↓
Redis Cache Layer
        ↓
Node API (read-only)
        ↓
React Dashboard
````

---

# 3. NODE API RESPONSIBILITIES

The Node API MUST:

* ONLY read from Redis
* NEVER run ML computations
* NEVER trigger training
* NEVER perform PCA generation
* NEVER mutate ML state

The ML worker remains the sole compute engine.

The API layer only exposes cached Redis state.

---

# 4. BACKEND STRUCTURE

```text
core/
└── node-api/
    ├── src/
    │   ├── index.ts
    │   │
    │   ├── routes/
    │   │   └── ml.ts
    │   │
    │   ├── redis/
    │   │   └── client.ts
    │   │
    │   ├── utils/
    │   │   ├── safeJsonParse.ts
    │   │   └── redisHelpers.ts
    │   │
    │   └── types/
    │       └── ml.ts
    │
    ├── package.json
    ├── tsconfig.json
    ├── Dockerfile
    └── .env
```

---

# 5. REDIS CONTRACT

The Node API MUST expose all ML worker Redis outputs.

## PCA KEYS

```text
pca:latest
pca:history
pca:components
pca:variance
pca:total_variance
pca:eigenvalues
pca:mean
pca:std
```

## DRIFT KEYS

```text
drift:score
drift:classification
```

## MODEL KEYS

```text
model:prediction
model:confidence
risk:latest
```

## OBSERVABILITY KEYS

```text
ml:heartbeat
ml:last_run
```

---

# 6. REDIS CLIENT

## FILE

```text
src/redis/client.ts
```

## REQUIREMENTS

* use `ioredis`
* connect using `REDIS_URL`
* log Redis connection status
* support Docker internal networking

Example:

```env
REDIS_URL=redis://redis:6379
```

---

# 7. REQUIRED UTILITIES

## SAFE JSON PARSER

## FILE

```text
src/utils/safeJsonParse.ts
```

## PURPOSE

Prevent API crashes from malformed Redis payloads.

---

## REDIS HELPERS

## FILE

```text
src/utils/redisHelpers.ts
```

## REQUIRED HELPERS

```ts
getJsonKey(key: string)
getStringKey(key: string)
```

These helpers centralize Redis parsing logic.

---

# 8. PRIMARY ENDPOINT (CRITICAL)

## ROUTE

```http
GET /api/ml/pca/summary
```

## PURPOSE

Single-request dashboard hydration endpoint.

The frontend should fetch this endpoint every ~5 seconds.

---

## REQUIRED REDIS FETCHES

```text
pca:latest
pca:components
pca:variance
pca:eigenvalues
pca:total_variance
pca:mean
pca:std
drift:score
drift:classification
model:prediction
model:confidence
ml:heartbeat
ml:last_run
```

---

## PERFORMANCE REQUIREMENT

Redis fetches MUST use:

```ts
Promise.all([...])
```

DO NOT sequentially await Redis requests.

---

## RESPONSE SHAPE

```json
{
  "projection": [],
  "components": [],
  "variance": [],
  "eigenvalues": [],
  "totalVariance": 0,
  "mean": [],
  "std": [],
  "drift": 0,
  "driftClassification": "Stable",
  "risk": "Low",
  "confidence": 0.98,
  "heartbeat": 1710000000,
  "lastRun": 1710000000
}
```

---

# 9. REQUIRED ENDPOINTS

## PCA

```http
GET /api/ml/pca/summary
GET /api/ml/pca/history
GET /api/ml/pca/projection
GET /api/ml/pca/components
GET /api/ml/pca/variance
GET /api/ml/pca/eigenvalues
```

---

## DRIFT

```http
GET /api/ml/drift
```

### RESPONSE

```json
{
  "drift": 0.42,
  "classification": "Moderate"
}
```

---

## RISK

```http
GET /api/ml/risk
```

### RESPONSE

```json
{
  "prediction": "Medium",
  "confidence": 0.91
}
```

---

## HEALTH

```http
GET /health
```

### RESPONSE

```json
{
  "status": "ok"
}
```

---

# 10. PCA HISTORY REQUIREMENTS

## ROUTE

```http
GET /api/ml/pca/history
```

## REQUIREMENTS

* read Redis list `pca:history`
* limit to latest 100 entries
* parse all JSON safely
* return chronological history buffer

---

# 11. FRONTEND BENEFITS

This architecture enables:

* single-fetch dashboard updates
* smooth polling
* animated PCA latent-space rendering
* drift overlays
* anomaly highlighting
* viridis-based visualizations
* low-latency UI updates
* reduced frontend complexity

---

# 12. NODE API ARCHITECTURE RULES (CRITICAL)

## STRICT REQUIREMENTS

The Node API MUST NEVER:

* trigger ML inference
* retrain models
* compute PCA
* write ML outputs
* modify Redis ML state

The Node API is a read-only cache exposure layer.

---

# 13. ML WORKER SAFETY REQUIREMENTS

The ML worker MUST:

* safely handle empty embeddings
* safely handle missing models
* safely handle failed runtime initialization
* safely bootstrap with insufficient data

---

## REQUIRED MODEL SAFETY

```python
if risk_model is not None:
    ...
else:
    risk_label = "Unknown"
    confidence = 0.0
```

---

## REQUIRED EMPTY PROJECTION SAFETY

```python
if len(projection) == 0:
    return
```

---

# 14. OBSERVABILITY REQUIREMENTS

The ML worker should continuously expose:

```text
ml:heartbeat
ml:last_run
```

## EXAMPLE

```python
store_value(
    "ml:heartbeat",
    int(time.time())
)

store_value(
    "ml:last_run",
    int(time.time())
)
```

---

# 15. DOCKER REQUIREMENTS

## CONTAINER NAME

```text
node-api
```

## BUILD CONTEXT

```yaml
build:
  context: ./core/node-api
```

---

# 16. FINAL PRIORITIES

## CRITICAL

* Redis → Node API mapping
* PCA summary endpoint
* safe Redis parsing
* model runtime fallback safety
* empty embedding bootstrap handling
* Promise.all Redis fetches
* `/app/models` safety

---

## SHOULD IMPLEMENT

* ML heartbeat
* ML observability
* health endpoint
* drift classification exposure

---

## FUTURE IMPROVEMENTS

* websocket streaming
* Redis pub/sub
* temporal drift analytics
* anomaly persistence
* model versioning
* inference tracing
* distributed ML workers
* Kubernetes readiness checks

```
```

