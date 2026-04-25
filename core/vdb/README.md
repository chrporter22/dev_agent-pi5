# VDB — Vector Database Service (PRD + System Spec)

**Version:** 2.0  
**System:** Distributed AI Stack  
**Target Hardware:** Raspberry Pi 5 (ARM64 + NVMe SSD)  
**Internal Service Port:** 8081  
**Network Scope:** internal_net only  
**Runtime:** Dockerized microservice  

---

# 1. Overview

OpenClaw VDB is a **persistent semantic memory service** designed for distributed AI workflows.

core/vdb/
│
├── app/
│   ├── main.py                  # FastAPI entrypoint (existing)
│   ├── vdb.py                   # core embed/upsert/search logic (existing)
│   ├── db.py                    # FAISS + SQLite index manager (existing)
│   ├── models.py                # SQLite schema + insert logic (existing)
│   ├── utils.py                 # embedding + hashing helpers (existing)
│   ├── config.py                # environment + constants (existing)
│
├── scripts/
│   ├── populate_volume.py       # NVMe preload script (existing)
│
├── tests/
│   ├── test_api.py              # API unit tests (existing)
│   ├── test_vdb.py             # core VDB logic tests (existing)
│   ├── test_performance.py      # latency + load test (existing)
│
├── data/
│   ├── instructions.json        # preload dataset (existing)
│   ├── db.sqlite                # SQLite persistence (runtime)
│   ├── index.bin                # FAISS serialized index (runtime)
│
├── Dockerfile                   # container build (existing)
├── requirements.txt             # dependencies (existing)
├── .env.example                 # environment config (existing)
└── README.md                    # PRD + system documentation (this file)

It provides:

- NVMe-backed vector persistence
- FAISS-powered similarity search
- SQLite as source-of-truth storage
- Redis integration for caching + ML acceleration
- Deterministic embedding retrieval layer

It is a **memory infrastructure service**, not an agent.

### VDB does NOT:
- perform LLM inference
- execute code
- manage queues
- interact with external APIs
- serve UI logic
- communicate directly with Telegram or GitHub

### VDB ONLY:
- stores embeddings
- retrieves semantic matches
- maintains FAISS index
- persists structured metadata
- serves internal API requests

---

# 2. System Architecture Role

## End-to-End System Flow

```text
Telegram
  → openclaw-bot
    → Redis queue: queue:jobs
      → openclaw-worker
        → openclaw-vdb (embed/search/upsert)
          → SQLite (source of truth)
          → FAISS (vector index cache)
          → Redis (hot cache + ML layer)
        → openclaw-ml (analysis + enrichment)
          → Redis ml:* outputs
            → node-api
              → React UI
````

---

## VDB Responsibilities

### Core Responsibilities

* Persistent embedding storage (SQLite)
* Fast ANN search (FAISS)
* Deterministic index rebuilds
* Metadata persistence
* Optional Redis cache sync

### Not Responsible For

* Job orchestration (worker handles this)
* LLM inference (LLM service handles this)
* UI/API aggregation (Node API handles this)
* ML analytics (ML service handles this)

---

# 3. API Specification (Internal Only)

## Base URL

```
http://openclaw-vdb:8081
```

* internal_net only
* no public exposure
* no host port binding

---

## POST /embed

Generate embedding vector

### Request

```json
{
  "text": "Create a PCA CLI tool"
}
```

### Response

```json
{
  "embedding": [0.12, -0.44, ...]
}
```

---

## POST /upsert

Store embedding + metadata

### Request

```json
{
  "text": "Build a regression model",
  "metadata": {
    "source": "worker",
    "timestamp": 1710000000
  }
}
```

### Behavior

* compute embedding (or accept precomputed)
* write to SQLite (WAL mode)
* update FAISS index
* optionally update Redis cache

### Response

```json
{
  "status": "ok",
  "id": "uuid"
}
```

---

## POST /search

Semantic similarity search

### Request

```json
{
  "query": "CSV PCA analysis",
  "top_k": 5
}
```

### Response

```json
{
  "matches": [
    {
      "id": "uuid",
      "score": 0.91,
      "text": "...",
      "metadata": {
        "source": "worker"
      }
    }
  ]
}
```

### Constraints

* cosine similarity (FAISS IndexFlatIP)
* top_k max: 10
* target latency: < 50ms (warm index)

---

## GET /health

```json
{
  "status": "healthy",
  "index_size": 1245,
  "redis_connected": true
}
```

---

# 4. Storage Architecture

## 4.1 Source of Truth (Primary)

```
/data/db.sqlite
```

Stores:

* embeddings
* raw text
* metadata
* timestamps

---

## 4.2 Vector Index (Derived Cache)

```
/data/index.bin
```

Stores:

* FAISS index state
* ID mapping
* search acceleration structure

---

## 4.3 Redis Layer (Acceleration Layer)

Redis is used for:

* caching search results
* storing ML outputs
* reducing FAISS load
* storing hot query results

### Example keys

```
cache:vdb:search:<hash>
ml:vdb:drift
ml:vdb:pca
ml:vdb:embedding_hot
```

---

# 5. Startup Lifecycle

On container boot:

1. Validate `/data`
2. Initialize SQLite (WAL mode enabled)
3. Load embeddings from SQLite
4. Rebuild FAISS index
5. Connect Redis (if available)
6. Load embedding model
7. Warm cache (optional)
8. Enter ready state

---

## Startup Target

* < 3 seconds for 10k embeddings
* deterministic rebuild from SQLite

---

# 6. Data Consistency Model

## Source of Truth Hierarchy

```
SQLite (truth)
   ↓
FAISS (derived index)
   ↓
Redis (cache layer)
```

---

## Recovery Rules

### If FAISS is lost or corrupted:

```
Rebuild ONLY from SQLite
```

### NEVER:

* rebuild from FAISS ❌
* treat Redis as persistent ❌

---

# 7. Security Model (Zero Trust Internal Service)

## Container Hardening

* non-root execution
* read-only root filesystem
* only `/data` writable
* cap_drop: ALL
* no-new-privileges
* memory limited (1GB)
* internal network only

---

## Network Isolation

### Allowed:

* openclaw-worker
* node-api

### Denied:

* internet access
* GitHub
* Telegram
* LLM service direct calls
* host network access

---

# 8. Performance Targets

## Search

* < 50ms (warm index)
* FAISS IP optimized

## Ingestion

* < 20ms per upsert (excluding embedding generation)

## Memory

* target steady state: < 600MB
* max container: 1GB

---

# 9. NVMe Storage Requirements

* Raspberry Pi 5 + PCIe NVMe HAT
* mounted persistent volume at `/data`
* expected throughput: 300–500MB/s

---

# 10. ML + Redis Integration Layer

VDB emits events to Redis for downstream ML services:

```
ml:vdb:embedding_updated
ml:vdb:drift_score
ml:vdb:search_stats
```

---

## ML Responsibilities (External Service)

* PCA analysis
* drift detection
* clustering
* embedding quality scoring

VDB ONLY stores results.

---

# 11. System Design Principles

* deterministic rebuilds
* SQLite = source of truth
* FAISS = disposable acceleration layer
* Redis = cache only
* no external dependencies at runtime
* strict separation of concerns
* stateless API layer over persistent storage

---

# 12. Acceptance Criteria

## Functional

* embeddings persist across restarts
* FAISS rebuilds correctly from SQLite
* search returns deterministic results
* Redis cache integration is optional and safe

---

## Performance

* < 50ms search latency (warm)
* stable ingestion under load
* no memory leaks

---

## Reliability

* full recovery after crash
* index always rebuildable from SQLite
* no dependency on Redis for correctness

---

## Security

* no outbound internet access
* no exposed ports externally
* internal-only service access
* no secret leakage in logs

---

# 13. Design Philosophy

A deterministic, NVMe-accelerated semantic memory engine for distributed AI systems.

It is:

* not an agent
* not an inference engine
* not a cache-only layer

It is the **memory backbone** of the system enabling:

* fast LLM context injection
* reduced token usage
* persistent semantic memory
* distributed AI coordination via Redis

---
