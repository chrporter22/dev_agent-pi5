# MASTER TODO LIST (WITH ML WORKER INTEGRATION)
---

## Phase 4 — Control Panel (pca-backend)

### 17) Build `pca-backend` container

- Nginx + React  
- Bind: `80:80`  

---

### 18) Configure Nginx routing

- `/` → React UI  
- `/api` → Node API  

---

### 19) Build React dashboard

- PCA scatter plot (PC1 vs PC2)  
- Dynamic component switching  
- Drift timeline  
- Risk panel  
- Covariance visualization (heat map)  

---

## Phase 5 — DevOps + Tooling

### 20) Create repo + CI/CD

- Use GitHub  

Add:
- Workflows  
- Container builds  

---

### 21) Update install.sh

- Fix model path for:
  - Qwen1.5  

- Ensure reproducibility  

---

## Phase 6 — External Integrations (LAST)

### Create Yahoo email

---

### Create Telegram account

---

## Key Insight (critical change)

ML is **NOT** part of:
- Frontend  
- Nginx  
- Node API  

It is a **parallel internal service** that:
- Pulls from VDB  
- Pushes to Redis  

---

## Final architecture after this TODO
```text

React UI
↓
pca-backend (nginx)
↓
node-api
↓
Redis ← ML Worker ← VDB
```
---
## Common mistakes to avoid (now that ML is added)

- Calling ML directly from React  
- Computing PCA inside Node API  
- Skipping Redis cache  
- Exposing ML container ports  
- Training model synchronously with requests
---

# DEV AGENT Pi

Secure Infrastructure-as-Code AI + Analytics Stack for Raspberry Pi 5 (ARM64)

Version: 1.0  
Target: Raspberry Pi 5 (16GB RAM)  
OS: Arch Linux ARM64  
Architecture: Zero-Trust, Least Privilege, Fully Containerized  

---

## Overview

DEV Pi is a secure, reproducible AI control plane and analytics stack designed to run entirely on a Raspberry Pi 5 using Docker.

It provides:

- Secure Telegram-controlled automation bot
- Local Qwen2-1.5B LLM inference (llama.cpp)
- SQLite-backed vector database
- PCA monitoring analytics pipeline and mission control
- Redis caching layer
- Node backend API
- React + Tailwind dashboard
- Nginx reverse proxy (only exposed service)

All components follow strict zero-trust and least-privilege security rules.

---

# Architecture

Telegram
→ openclaw-bot
→ openclaw-llm (Qwen2-1.5B local inference)
→ openclaw-vdb (SQLite vector DB)
→ node-api
→ ml
→ pca-backend (mission control monitoring | nginx)

---
# Full Stack Bootstrap

Welcome to **Dev Pi**, a secure, NVMe-backed LLM + Vector Database container stack for Raspberry Pi 5.  
This project provides deterministic, reproducible deployment for long-term semantic memory and context retrieval for LLMs.

> NVMe persistence is used for the VDB data (`db.sqlite` + `index.bin`).

---

## 2️⃣ Cloning the Repository

```bash
git clone https://github.com/chrporter22/dev_agent-pi5.git
cd dev_agent-pi5 
```

Optionally, update submodules:

```bash
git submodule update --init --recursive
```

---

## 3️⃣ Environment Setup

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` to configure any secrets or custom settings.  
> **Note:** `.env` and secret files are ignored by git.

---

## 4️⃣ Install Dependencies & Bootstrap

Ensure your Raspberry Pi 5 has:

- Arch Linux ARM64
- Docker & Docker Compose
- 16GB RAM
- NVMe SSD mounted (e.g., `/mnt/nvme`)

Run the installer to validate architecture, memory, Docker, volumes, and download the LLM model:

```bash
./install.sh
```

This script will:

- Validate host architecture & memory
- Validate Docker & Docker Compose
- Create required Docker volumes
- Download & verify LLM model
- Build all containers deterministically
- Start the stack

---

## 5️⃣ Initialize Vector Database

Populate embeddings and NVMe persistence:

```bash
docker compose run --rm openclaw-vdb python /app/populate_volume.py
```

This ensures:

- SQLite DB and FAISS index are created
- Sample embeddings are loaded
- NVMe persistence is verified

---

## 6️⃣ Start All Services

Bring up the full stack:

```bash
docker compose up -d
```

Verify running containers:

```bash
docker compose ps
```

Expected containers:

- `openclaw-bot`
- `openclaw-llm`
- `openclaw-vdb`
- `redis`
- `pca-backend` 
- `node-api`

---

## 7️⃣ Health Checks

- **VDB:**

```bash
docker compose exec openclaw-vdb curl http://localhost:8081/health
```

- **Redis:**

```bash
docker compose exec redis redis-cli ping
```

- **LLM logs:**

```bash
docker compose logs -f openclaw-llm
```

### Notes

- Persistent data is stored in Docker volumes:
  - `openclaw_llm_model`
  - `openclaw_vdb_data`
  - `bot-redis-data`
- No containers have outbound internet access
- All API endpoints are internal-only
- VDB retrieval latency: <50ms for 10k entries
- LLM remains stateless; long-term memory persisted in VDB
---
# Container Layout

Core Dev:
- openclaw-bot
- openclaw-llm
- openclaw-vdb

PCA Pipeline:
- pca-ml
- pca-redis
- pca-backend
- pca-frontend (nginx inside frontend)
---

# Security Model

## Global Rules

- All containers run as non-root
- read_only: true (except required writable dirs)
- cap_drop: ALL
- no-new-privileges: true
- No docker.sock mounts
- No privileged containers
- No host filesystem mounts
- No access to Repo A from bot
- Secrets only via environment variables
- No WiFi credentials or Pi passwords in containers

## Network Segmentation

internal_net:
- bot
- llm
- vdb
- ml
- redis
- backend

frontend_net:
- nginx
- frontend
- backend

Only nginx exposes a port to host.

---

# Bot Workflow

Telegram Owner
→ /build <feature>
→ send instructions
→ Bot sends to LLM
→ LLM returns structured JSON
→ Bot enqueues job
→ Worker creates branch in Repo B
→ Commits task file
→ Opens PR
→ Repo B CI generates project
→ Owner approves PR

No direct commits to main branch.

---

# Deployment

Set:
TELEGRAM_TOKEN
GITHUB_TOKEN (fine-grained, Repo B only)
ALLOWED_USER
SANDBOX_REPO

## Performance Targets (Pi 5 16GB)

- LLM: 6–8GB
- VDB: 1GB
- ML: 2GB
- Redis: 512MB
- Backend: 512MB
- Frontend: 512MB
- Bot: 512MB

Peak < 13GB total

## Acceptance Criteria
- All containers run non-root
- No unintended public ports
- LLM responds locally
- VDB stores embeddings
- PCA pipeline executes end-to-end
- Redis caching functional
- Telegram bot creates PRs
- No direct commits to main
- Repo A inaccessible from containers
- Secrets not logged

## Reproducibility

- Cloning Repo A + running:
```bash
docker compose up
```

- Launches a fully working environment on any ARM64 Linux system.
- Sandbox Repo B can be cloned independently without secrets.

## Zero Trust Guarantees
The system:
- Does not expose Docker socket
- Does not expose SSH
- Does not expose host filesystem
- Does not store WiFi credentials
- Does not allow arbitrary shell execution
- Does not allow Repo A access

## Future Extensions
- Dedicated queue container
- Audit log store
- Policy engine
- Context-aware LLM builds

## Multi-user RBAC
- Signature verification on PR merge

