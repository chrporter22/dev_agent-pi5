# LLM CONTAINER (openclaw-llm)

Local-Only Structured Inference Engine  
Target: Raspberry Pi 5 (16GB RAM, ARM64, Arch Linux)  
Engine: llama.cpp (ARM64 optimized)  
Model: Qwen2-1.5B-Instruct (GGUF Q4_K_M)  
Security Model: Zero Trust  

---

# Purpose

The openclaw-llm container is a **pure inference microservice** used exclusively by openclaw-bot.

It:

- Loads a local GGUF LLM model
- Accepts structured POST requests
- Returns strict JSON responses
- Has zero outbound internet access
- Is not autonomous
- Is not an orchestration agent
- Cannot access GitHub, Telegram, Redis, or host system

Architectural Flow:

Telegram  
→ openclaw-bot  
→ openclaw-llm  
→ openclaw-bot  
→ GitHub Repo B  

The LLM is subordinate to the bot and never makes execution decisions.

---

# Model Specification

Model: Qwen2-1.5B-Instruct  
Format: GGUF (Q4_K_M)  
Approx Size: ~4GB  
Context Window: 2048 tokens  

Rationale:
- Fits within Pi 5 memory limits
- Balanced reasoning quality and speed
- <5 second structured parsing latency target

Recommended Runtime Settings:
- Threads: 6–8
- Memory allocation: 6–8GB
- --ctx-size 2048
- --mlock enabled
- ARM NEON optimization enabled

Model Path (inside container):

/models/qwen2-1_5b-instruct-q4_k_m.gguf

---

# API Specification

Base URL (internal only):

http://openclaw-llm:8080

The container does NOT expose ports to the host.

---

## POST /parse

Structured instruction parsing endpoint.

Request:

{
  "instruction": "Create a CLI tool that reads CSV and runs PCA"
}

Response:

{
  "type": "cli_tool",
  "language": "python",
  "features": ["pca", "csv"],
  "tests": true,
  "description": "CLI tool for PCA on CSV datasets"
}

Requirements:

- Must return valid JSON only
- No markdown
- No explanations
- No prose outside JSON
- Schema must be deterministic
- Latency target: <5 seconds

---

## POST /completion (Future Optional)

Request:

{
  "prompt": "...",
  "n_predict": 256,
  "temperature": 0.7
}

Response:

{
  "completion": "..."
}

This endpoint is optional and not required for MVP.

---

# Security Model

Zero Trust enforcement.

The LLM container:

- Runs as non-root user
- Has read-only root filesystem
- Drops all Linux capabilities
- Uses no-new-privileges
- Has pids_limit enforced
- Has memory limits enforced (8GB)
- Has no docker.sock
- Has no privileged flags
- Has no host mounts
- Has no outbound internet
- Exposes no public ports

---

# Network Isolation

The container must:

- Attach only to internal_net
- Not attach to outbound_net
- Not attach to frontend_net
- Not expose ports to host

Only openclaw-bot may call the LLM.

The LLM must not:

- Access Redis
- Access GitHub
- Access Telegram
- Access external DNS
- Reach the internet

Isolation is achieved through Docker network segmentation.

---

# Persistence

Docker Named Volume:

openclaw_llm_model

Mounted:

/models

Rules:

- Volume is read-only inside container
- No host bind mounts
- Model persists across rebuilds
- No runtime downloads allowed

Example model file:

/models/qwen2-1_5b-instruct-q4_k_m.gguf

---

# Resource Limits (Pi 5 – 16GB)

Memory Limit: 8GB  
Threads: 6–8  
Context Window: 2048  
PIDs: 200  
Swap: Disabled  

System Target:

Total system peak usage across all containers <13GB.

---

# Deployment

Build and run via Docker Compose:

```bash
docker compose up -d
```

Verification:

```bash
docker inspect openclaw-llm
```

Confirm:

- Not privileged
- ReadOnlyRootFilesystem: true
- CapDrop: ALL
- No exposed ports
- Attached only to internal_net
- Memory limit enforced
- Running as non-root

---

# Acceptance Criteria

Deployment:

- Container launches successfully
- Model loads from Docker volume
- Runs as non-root
- Root filesystem read-only
- No outbound network
- No public ports

Functional:

- /parse returns valid JSON
- Bot can successfully call LLM
- Latency <5 seconds
- Memory usage within limit

Security:

- No shell execution exposed
- No arbitrary code execution
- No access to host filesystem
- No access to GitHub API
- No access to Telegram API
- No secret environment variables

---

# Zero Trust Guarantees

The LLM cannot:

- Access Repo A
- Access Repo B
- Access GitHub
- Access Telegram
- Access Redis
- Access host filesystem
- Execute arbitrary shell commands
- Mount additional volumes
- Make outbound internet calls

The LLM only:

- Accepts structured POST requests
- Loads model from /models
- Performs inference
- Returns structured JSON

---

# Design Philosophy

- Stateless (except model in memory)
- Deterministic JSON generator
- No autonomy
- No orchestration logic
- Not an agent
- Local-only inference engine

It is a controlled parsing engine used by openclaw-bot.

---

# Architectural Role

Control Plane:

Telegram  
→ openclaw-bot  
→ openclaw-llm  
→ GitHub Repo B  

The LLM is never the decision-maker.  
It is a constrained subordinate service.

---

# Future Extensions

- Grammar-constrained JSON output
- Schema validation enforcement
- Context-aware parsing using vector DB
- Embedding endpoint
- Audit logging
- Token usage limits
- Output policy enforcement
- Structured prompt templates

---

# Security Note

No outbound firewall rules are required for Telegram or GitHub.

The LLM container has:
- No network route to external services
- No public port exposure
- No secret tokens
- No credentials

Security is achieved through strict container isolation and network segmentation.

---

