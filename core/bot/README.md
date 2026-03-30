# BOT CONTAINER (openclaw-bot)

# OpenClaw Bot

Secure Telegram-Controlled Data Science Agentic AI Stack 
Pi Architecture

Target: Raspberry Pi 5 (ARM64) & linux-rpi  
Memory Limit: 512MB  
Security Model: Zero Trust

---

# Purpose

Serves as the secure orchestration layer between:

→ Telegram
→ Local Qwen LLM
→ GitHub Sandbox Repo (Repo B)

It never:
- Accesses Source Infrastructure as Code
- Executes shell commands
- Mounts host filesystem
- Exposes ports
- Runs as root

---

# Security Hardening
Container Settings:
- Non-root user
- read_only: true
- cap_drop: ALL
- no-new-privileges: true
- pids_limit enforced
- mem_limit: 512MB
- No docker.sock
- No privileged flags
- No host mounts

Outbound HTTPS only:
- Telegram API
- GitHub API

---

# Supported Commands

Owner-only (RBAC enforced via ALLOWED_USER):
/status  
/listpr  
/approvepr <PR#>  
/build <feature_name>  
/jobs  

Rate limit: 10 commands per minute

---

# Build Flow
1. Owner sends:
   /build my_tool

2. Owner sends instructions

3. Bot:
   - Sends instructions to local LLM
   - Validates returned JSON schema
   - Enqueues job in Redis
   - Worker creates branch:
     feature/<uuid>
   - Commits /tasks/<uuid>.json
   - Opens Pull Request

No direct commits to main.

---

# Environment Variables
Required:

TELEGRAM_TOKEN  
GITHUB_TOKEN (fine-grained, Repo B only)  
ALLOWED_USER  
SANDBOX_REPO  
REDIS_URL  
LLM_ENDPOINT  

No other secrets permitted.

---

# Job Queue
- Redis-backed
- UUID-based job IDs
- Retry up to 3 times
- Failed jobs tracked
- /jobs displays status

---

# LLM Integration
Bot sends:

POST http://openclaw-llm:8080/parse

Receives structured JSON task schema.

Bot validates schema before PR creation.

LLM container:
- Internal network only
- No GitHub access
- No outbound internet

---

# Repo B Structure

repo-b/
├── tasks/
├── generated/
├── templates/
└── .github/workflows/task-runner.yml

Bot writes only to tasks/ via PR.

---

# Deployment

```bash
cp .env.example .env
docker compose up -d
```

## Verification
Ensure:
```bash
docker inspect openclaw-bot
```

Confirm:
- Not privileged
- ReadOnlyRootFilesystem: true
- No mounts
- No exposed ports
- CapDrop: ALL

## Zero Trust Guarantees
The bot:
- Cannot access host
- Cannot access Repo A
- Cannot execute arbitrary code
- Cannot open public ports
- Cannot read WiFi credentials
- Cannot access SSH keys
It only:
- Polls Telegram
- Calls internal LLM
- Calls GitHub API
- Creates PRs in Repo B
