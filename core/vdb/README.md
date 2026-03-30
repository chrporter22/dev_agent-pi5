# VDB (Vector Database Container)

Version: 1.0  
Target: Raspberry Pi 5 (16GB RAM, ARM64, Arch Linux)  
Internal Port: 8081  

---

## 1. Overview

VDB is a secure, NVMe-backed vector database container that provides:

- Long-term semantic memory
- Context retrieval before LLM inference
- Token reduction
- Deterministic similarity search
- Zero Trust isolation
- Persistent storage on NVMe

It is **not an agent**.  
It does **not perform inference**.  
It does **not access GitHub or Telegram**.  
It does **not communicate directly with the LLM**.  

It is a strictly subordinate internal service.

---

## 2. Architecture Role

Control Flow:

Telegram  
→ openclaw-bot  
→ openclaw-vdb (context retrieval)  
→ openclaw-llm (augmented prompt)  
→ openclaw-bot  
→ Repo B  

The VDB provides:

- Top-K similarity search
- Persistent long-term memory
- Reduced token usage
- Faster inference
- Deterministic context retrieval

LLM remains stateless.

---

## 3. API (Internal Only)

Base URL:

http://openclaw-vdb:8081

This service is available **only on internal_net**.  
No public port exposure.

---

### POST /embed

Request:

```json
{
  "text": "Create a PCA CLI tool"
}
```

Response:

```json
{
  "embedding": [float, float, ...]
}
```

Used internally before upsert.

---

### POST /upsert

Request:

```json
{
  "id": "uuid",
  "text": "Original instruction",
  "embedding": [...],
  "metadata": {
    "source": "telegram",
    "timestamp": 1710000000
  }
}
```

Behavior:

- Stores embedding
- Persists metadata
- Writes to SQLite (WAL mode)
- Updates in-memory FAISS index

Response:

```json
{
  "status": "ok"
}
```

---

### POST /search

Request:

```json
{
  "query": "Build a CSV PCA analyzer",
  "top_k": 5
}
```

Response:

```json
{
  "matches": [
    {
      "id": "...",
      "score": 0.89,
      "text": "...",
      "metadata": {...}
    }
  ]
}
```

Constraints:

- Cosine similarity search
- Deterministic ranking
- top_k capped at 10
- Latency target < 50ms for 10k entries

---

### GET /health

Response:

```json
{
  "status": "healthy",
  "index_size": 1245
}
```

---

## 4. Storage

Docker Volume:

openclaw_vdb_data

Mounted at:

/data

Files stored:

- /data/db.sqlite
- /data/index.bin
- SQLite WAL files

All persistent data stored on NVMe.

No host bind mounts inside container.

---

## 5. Startup Flow

On container startup:

1. Validate /data directory
2. Initialize SQLite database
3. Enable WAL mode
4. Load all embeddings
5. Rebuild FAISS index
6. Load embedding model
7. Enter ready state

Startup target:  
< 3 seconds for 10k entries

---

## 6. Security Model (Zero Trust)

Container Hardening:

- Non-root user
- read_only: true
- Writable only /data
- cap_drop: ALL
- security_opt: no-new-privileges:true
- mem_limit: 1GB
- pids_limit: 100
- No docker.sock
- No privileged mode
- No outbound internet
- No public ports
- internal_net only

Network Policy:

- Accessible from:
  - openclaw-bot
  - pca-backend
- Not accessible from:
  - openclaw-llm
  - Internet
  - Host network

VDB cannot:

- Access GitHub
- Access Telegram
- Access Repo A or Repo B
- Execute shell commands
- Mount new volumes
- Perform inference

VDB only:

- Accepts embedding/search requests
- Stores vectors
- Returns similarity matches

---

## 7. Memory Budget

Container memory limit: 1GB

Expected usage:

- Embedding model: ~200MB
- FAISS index (10k entries): ~200MB
- SQLite + WAL + API: ~200MB

Target steady state:

< 600MB

System-wide container peak target:

< 13GB

---

## 8. NVMe Requirements

Hardware:

- Raspberry Pi 5
- PCIe M.2 HAT
- NVMe SSD
- PCIe Gen 2 enabled

Target performance:

- ~400–500 MB/s sequential
- Low latency random reads
- Stable sustained write performance

Example host mount:

/mnt/nvme/openclaw_vdb

Docker named volume backed by NVMe.

---

## 9. Token Optimization Strategy

Instead of sending entire chat history:

- Retrieve top 3–5 semantically similar instructions
- Inject concise context
- Keep prompt under ~800 tokens
- Preserve ~1200 tokens for generation

Benefits:

- Reduced memory pressure
- Lower latency
- Prevent context overflow
- Deterministic retrieval

---

## 10. Acceptance Criteria

Deployment:

- Runs as non-root
- Root filesystem read-only
- Only /data writable
- Attached only to internal_net
- No exposed ports
- NVMe persistence verified

Functional:

- Embeddings stored correctly
- Similarity search accurate
- Retrieval latency < 50ms (10k entries)
- Data survives restart
- Context injected before inference

Security:

- No outbound internet
- No secret environment variables
- No access to LLM
- No access to GitHub or Telegram

Performance:

- Memory < 1GB
- System peak < 13GB
- Stable NVMe read/write
- Index rebuild successful on restart

---

## 11. Design Philosophy

- Deterministic
- Persistent
- Fast
- Memory-efficient
- Non-autonomous
- Strictly subordinate service
- NVMe-accelerated semantic memory layer
