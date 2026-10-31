# DEV AGENT Pi — Product Requirements Document (PRD)

Version: 2.0
Service: dev_agent-pi5
Runtime: Docker Compose (6 services) on Raspberry Pi 5 (ARM64, 16GB, Arch Linux)
Scope: Telegram frontend to a user-owned AI gateway, with git/PR automation
Status: Phases 1–4 complete (chat + build + containers + Redis ACLs + ML cleanup + dashboard fixes); Phase 5 (CI/CD) pending.

---

## 1. Purpose

`dev_agent-pi5` is a zero-trust, fully containerized Telegram coding interface. The bot receives natural-language instructions from a single authorized user, the worker delegates LLM work to an external `~/ai-gateway` (LiteLLM), and the worker performs the resulting git actions directly so pull requests land in the user's repositories for review.

This repo is the **frontend and git worker**. It does not perform LLM inference. The gateway owns inference; this repo transports requests and executes git actions.

---

## 2. Design principles

- **Delegate inference.** No model weights on the Pi. The gateway owns all LLM capability. This keeps the deploy footprint small, the security surface auditable, and the model swappable per chat (`/model`).
- **Zero trust at every layer.** The network is hostile. Every request re-authenticates. Every secret flows through env on a backend service. The frontend never holds a third-party credential.
- **No API keys in any frontend.** The Telegram bot and the PCA dashboard hold zero third-party credentials. Every secret is consumed server-side.
- **Single user.** Enforced by `ALLOWED_USER` (numeric Telegram user ID) on every command. Rate-limited at 10 commands/min/user.
- **Per-service datastore isolation.** The Redis ACL is this repo's row-level security. Each service authenticates as its own user with its own key-pattern scope. `default` is `off`.
- **Smallest dependency surface that works.** The ML pipeline is numpy-only after the Keras/TFLite drop (Phase 4). No `scipy`, no `scikit-learn`, no `tensorflow` in the hot path.
- **The bot never writes to `main`.** All branches are `dev-agent/<job-id-prefix>`. The user merges from the GitHub UI.

---

## 3. Architecture

### 3.1 Request flow

```
Telegram
   |
   v
openclaw-bot (commands + dictation, RBAC + rate-limited)
   |   - bot.py: polling, command dispatch, RBAC gate, queue
   v
Redis (queue + cache + chat history + ML state)
   |   - per-service ACLs: bot / worker / ml / nodeapi (default off)
   v
openclaw-worker
   |-- /build:  clone -> plan_changes (gateway) -> apply -> commit -> push -> open_pr
   '-- /chat:   chat (gateway) -> append history -> _chunk_send reply
   v
GitHub REST API (GITHUB_TOKEN, /build only)

Analytics (dormant until a data source is wired):
openclaw-ml -> Redis -> node-api -> pca-backend (nginx :80)
```

### 3.2 Services

| Service            | Role                                                              | Network             | Redis user |
|--------------------|-------------------------------------------------------------------|---------------------|------------|
| `redis`            | Job queue, chat history, ML state, cache (per-service ACLs)       | internal            | n/a        |
| `openclaw-bot`     | Telegram polling, command parsing, RBAC, rate limit, job queuing  | internal + outbound | `bot`      |
| `openclaw-worker`  | Queue consumer; `/build` = git + gateway + PR; `/chat` = gateway | internal + outbound | `worker`   |
| `openclaw-ml`      | Background analytics: PCA (numpy), drift, rules-based risk       | internal            | `ml`       |
| `node-api`         | Read-only Express layer serving ML Redis state                    | internal            | `nodeapi`  |
| `pca-backend`      | React + Tailwind dashboard behind nginx                           | internal + outbound (only public port :80) | none |

### 3.3 Service processes

- **Two processes share the `core/bot` image.** `openclaw-bot` runs `python bot.py` (default); `openclaw-worker` overrides the command to `python queue_worker.py`. Both processes consume the same env and the same `core/bot/` source tree.
- **`openclaw-ml` runs a single Python loop.** `python ml_worker.py`. No HTTP API.
- **`node-api` runs Express on port 3000**, exposed only to the internal network and to `pca-backend` over the compose network.
- **`pca-backend` runs nginx on port 80**, the only public ingress. Serves the React dashboard built with Vite.

### 3.4 Container hardening

Every service has:

- `read_only: true` on root FS; tmpfs for writable surfaces only (`/tmp`, `/var/run`, `/var/cache/nginx`, `/sandbox`, `/app/data`, `/usr/local/etc/redis`).
- `cap_drop: ALL`, `security_opt: no-new-privileges: true`.
- Non-root users (`botuser`, `mluser`, `nginx`).
- `pids_limit` and `mem_limit` per service.
- Internal Docker network with `internal: true`; only `pca-backend` exposes a port.
- No docker.sock, no host mounts, no privileged flags.

---

## 4. Per-service spec

### 4.1 `core/bot` — Telegram frontend (`openclaw-bot` + `openclaw-worker`)

**Image:** `python:3.11-slim` + `git` CLI + `botuser` (non-root).

**Modules:**

| File                       | Purpose                                                                              |
|----------------------------|--------------------------------------------------------------------------------------|
| `bot.py`                   | Telegram polling, command dispatch, RBAC, rate limit, job queuing.                   |
| `queue_worker.py`          | Worker main loop; branches on `job_type` for build vs chat.                          |
| `ai_gateway_client.py`     | `parse_instruction` (legacy planner), `chat` (free text), `plan_changes` (build JSON). Shared retry helper. |
| `chat_store.py`            | Redis wrapper for `chat:{chat_id}:history` (LIST, trim to N) and `chat:{chat_id}:model` (STRING). |
| `telegram_sender.py`       | `_chunk_send(chat_id, text)` — splits on `\n\n` boundaries, ≤ `TELEGRAM_MAX_CHARS` per message. |
| `github_client.py`         | `clone_or_pull`, `create_branch`, `commit_all`, `push`, `open_pr`, `list_prs`, `get_pr`, `merge_pr`. Git CLI + REST API. |
| `rate_limiter.py`          | Redis-backed sliding-window rate limiter (10/min/user).                              |
| `healthcheck.py`           | TCP-reachability check on `AI_GATEWAY_BASE_URL`. Used by the worker's container healthcheck. |
| `config.py`                | Module-level env reads + defaults.                                                   |

**Outbound:**

- Bot: Telegram API only.
- Worker: Telegram API (for replies), `~/ai-gateway` (LLM), GitHub REST API (for PRs).

### 4.2 `core/ml` — Analytics (`openclaw-ml`)

**Image:** `python:3.11-slim` + `mluser` (non-root).

**Pipeline (numpy + rules, no model):**

1. **Intake** — `_load_embeddings()` stub returns `None` while no data source is wired. The loop is dormant by design.
2. **PCA** — `pca_engine.compute_pca(embeddings)` computes top-`k = 5` components via `np.linalg.eigh` on the standardized covariance matrix. Persists `mean`, `components`, `variance`, `eigenvalues`, `n_samples`, `n_features`.
3. **Drift** — `drift_detector.compute_drift(embeddings)` returns centroid shift + variance shift, averaged. Outputs `drift:score` and `drift:classification` (`Stable` / `Moderate` / `High` / `Critical`).
4. **Risk** — `risk_classifier.classify_risk(drift_score)` returns `(label, confidence)` where label is one of `Low` / `Medium` / `High` / `Critical` and confidence is the normalized band-edge distance in `[0.5, 1.0]`. Deterministic rule, not a learned probability.
5. **Heartbeat** — `ml:heartbeat` and `ml:last_run` are written every cycle so the dashboard's WorkerCard stays accurate even when no data flows.

**Modules:**

| File                       | Purpose                                                                              |
|----------------------------|--------------------------------------------------------------------------------------|
| `ml_worker.py`             | Loop: fetch -> PCA -> drift -> risk -> Redis. Always writes heartbeat.                |
| `pca_engine.py`            | Pure numpy PCA (covariance + eigh).                                                  |
| `drift_detector.py`        | Centroid + variance drift (single window).                                           |
| `risk_classifier.py`       | Rules-based risk + band-edge confidence.                                             |
| `redis_store.py`           | Redis client (user `ml`, scoped key patterns).                                       |
| `config.py`                | Env reads + thresholds + loop interval.                                              |

**Dependencies:** `numpy`, `redis`, `requests`. (Phase 4 removed `tensorflow`, `tflite-runtime`, `scikit-learn`, `joblib`, `scipy`.)

### 4.3 `core/node-api` — Read-only Express over Redis

**Image:** Node 22. Express 4. TypeScript strict.

**Endpoints** (under `/api/ml/`):

| Method | Path              | Reads from Redis                                  | Returns |
|--------|-------------------|---------------------------------------------------|---------|
| GET    | `/pca/summary`    | `pca:*`, `drift:score`, `model:prediction`, `model:confidence` | Full PCA summary |
| GET    | `/pca/history`    | `pca:history` (LIST, latest 100)                  | JSON-parsed history |
| GET    | `/pca/projection` | `pca:latest`                                      | Projected points |
| GET    | `/pca/components` | `pca:components`                                  | Eigenvectors |
| GET    | `/pca/variance`   | `pca:variance`                                    | Explained variance ratios |
| GET    | `/pca/eigenvalues`| `pca:eigenvalues`                                 | Eigenvalues |
| GET    | `/drift`          | `drift:score`, `drift:classification`             | Drift + bucket |
| GET    | `/risk`           | `model:prediction`, `model:confidence`            | Risk + confidence |

**Redis client:** explicit `REDIS_HOST` / `REDIS_PORT` / `REDIS_USER` (`nodeapi`) / `REDIS_PASSWORD` fields. No `REDIS_URL`.

**Command posture:** `nodeapi` is **read-only by command set** (`+get +hget +hgetall +lrange +zrange +zrevrange +exists +type +ttl +scan -@all`), not just by key patterns.

### 4.4 `core/pca-backend` — React dashboard (only public ingress)

**Image:** `nginx:1.27-alpine`. React 18 + Vite 5 + Recharts + Tailwind.

**Build:** `tsc && vite build`. Output in `dist/`. Nginx serves the SPA and proxies `/api/` to `node-api:3000` (proxy_pass without trailing slash so the `/api/` prefix is preserved).

**Components:**

| File                                       | Purpose                                                       |
|--------------------------------------------|---------------------------------------------------------------|
| `src/main.tsx`                             | React entry; mounts `<App />` under `<QueryClientProvider>`.  |
| `src/App.tsx`                              | Renders the `Dashboard` page.                                 |
| `src/pages/Dashboard.tsx`                  | Composes cards + charts, polls every 5s via `usePcaSummary`. |
| `src/components/cards/RiskCard.tsx`        | Risk label + rule-margin confidence. Handles undefined.       |
| `src/components/cards/DriftCard.tsx`       | Drift score + classification.                                 |
| `src/components/cards/WorkerCard.tsx`      | Worker liveness from `ml:heartbeat`.                          |
| `src/components/cards/VarianceSummaryCard.tsx` | Explained variance + eigenvalue summary.                   |
| `src/components/charts/*`                  | PCA Explorer, VarianceChart, EigenvalueChart, HistoryTimeline.|
| `src/types/ml.ts`                          | `PcaSummary` and `HistoryPoint`. `risk` and `confidence` are optional (Phase 4 decision #14: dashboard must render when Redis is fresh). |
| `src/hooks/usePcaSummary.ts`               | TanStack Query wrapper around `/pca/summary`.                  |
| `nginx.conf`                               | SPA fallback + `/api/` proxy to `node-api`.                   |

### 4.5 `redis` — Datastore with per-service ACLs

**Image:** `redis:7-alpine`. `read_only: true` on root FS. Substituted ACL lives on tmpfs.

**Files:**

- `redis/redis.conf` — `bind 0.0.0.0`, `appendonly no`, `save ""`, `aclfile /usr/local/etc/redis/users.acl`, dangerous commands (`FLUSHDB`, `FLUSHALL`, `KEYS`, `CONFIG`, `SHUTDOWN`, `DEBUG`) renamed to empty.
- `redis/users.acl.template` — `default off`; `bot`, `worker`, `ml`, `nodeapi` users with key patterns and command scopes. Passwords are `${REDIS_PASSWORD_*}` placeholders.
- `redis/entrypoint.sh` — `sed` substitutes the password placeholders from container env, `chmod 644`s the substituted ACL, `exec redis-server /usr/local/etc/redis/redis.conf`.

---

## 5. Bot commands

Owner-only (`ALLOWED_USER` enforced). Rate limit: 10 commands/minute/user.

| Command                          | Purpose                                                              |
|----------------------------------|----------------------------------------------------------------------|
| `/build [owner/repo] <feature>`  | Full coding workflow. Push branch + open PR. If repo omitted, uses `DEFAULT_REPO`. |
| `/chat <text>`                   | Dictation. Free-text conversation with the gateway. History maintained. |
| `/pr list`                       | List open PRs from bot-created branches.                              |
| `/pr <url\|num>`                 | Show a bot PR's status and metadata.                                  |
| `/pr approve <url\|num>`         | Merge a bot PR (sends merge request).                                 |
| `/jobs`                          | List recent jobs and statuses.                                        |
| `/job <id>`                      | Status + result for a specific job.                                   |
| `/status`                        | System health (queue depth, processing, dead-letter, worker heartbeat). |
| `/clear`                         | Wipe your chat history from Redis.                                    |
| `/model <name>`                  | Set per-chat model override for `/chat` jobs only.                    |

Anything else returns the help menu.

---

## 6. Workflows

### 6.1 Build flow (`/build [owner/repo] <feature>`)

1. **Parse** — Bot extracts `repo` (optional) + `instruction` (required). Missing instruction → usage reply.
2. **Enqueue** — Push `{id, chat_id, type: "build", repo, instruction, ts}` to Redis `queue:jobs`.
3. **Dequeue** — Worker `brpoplpush` from `queue:jobs` → `queue:processing`.
4. **Status** — Mark job `running` in Redis (`jobs:running` zset).
5. **Sandbox** — `github_client.clone_or_pull(repo, SANDBOX_DIR)`. Idempotent — pulls if exists.
6. **Branch** — `github_client.create_branch(SANDBOX_DIR, "dev-agent/<job-id-prefix>")`.
7. **Plan** — `ai_gateway_client.plan_changes(instruction, repo_context)` — returns `{files: [{path, action, content}]}`.
8. **Apply** — Write/modify/delete files in the sandbox. Path-traversal guarded: reject `..`, absolute paths, or paths that resolve outside `SANDBOX_DIR`.
9. **Commit** — `github_client.commit_all(SANDBOX_DIR, message)`. Returns `False` if no changes — worker marks complete and skips push.
10. **Push** — `github_client.push(SANDBOX_DIR, branch_name)`.
11. **PR** — `github_client.open_pr(repo, branch_name, base, title, body)` via GitHub REST API.
12. **Reply** — Send `Job <id> — PR opened: <url>` to Telegram.
13. **Cleanup** — Mark job `complete`, `lrem` from `queue:processing`.

On any git/gateway failure: send error to Telegram, mark job `failed`. No retry — user re-runs `/build` if needed.

**Plan prompts:** `plan_changes` instructs the gateway to include `.github/workflows/*.yml` (Docker build + unit tests) when adding new code. The worker carries the file content verbatim.

### 6.2 Chat flow (`/chat <text>`)

1. **Parse** — Bot extracts `instruction`. Missing → usage reply.
2. **Enqueue** — Push `{id, chat_id, type: "chat", instruction, ts}` to Redis.
3. **Dequeue** — Worker `brpoplpush`.
4. **History** — `ChatStore.history(chat_id)` → last 20 turns (`[{role, content, ts}, ...]`).
5. **Chat** — `ai_gateway_client.chat(messages, system_prompt, model=...)` — `/v1/chat/completions` with the conversation, no `response_format`. Model comes from per-chat override or `AI_GATEWAY_MODEL`.
6. **Persist** — Append user turn + assistant turn via `ChatStore.append`. List is trimmed to `CHAT_HISTORY_MAX_TURNS`.
7. **Reply** — `_chunk_send(chat_id, response_text)` — splits on `\n\n` boundaries, ≤ `TELEGRAM_MAX_CHARS` per message.
8. **Cleanup** — Mark job `complete`.

On failure: send `Chat failed: <err>` to Telegram, mark `failed`. No retry.

### 6.3 PR review flow (`/pr ...`)

- `/pr list` — list open PRs from bot-created branches across the user's accessible repos.
- `/pr <url|num>` — show a bot PR's status, base, head, diff summary.
- `/pr approve <url|num>` — call `github_client.merge_pr`; handles 405 (branch protection) gracefully and reports it back.

---

## 7. Data model

### 7.1 Redis keys

| Key pattern                         | Type | Owner (writer) | Reader          | Purpose |
|-------------------------------------|------|----------------|-----------------|---------|
| `queue:jobs`                        | LIST | `bot`          | `worker`        | Pending jobs (LPUSH on enqueue, BRPOPLPUSH on dequeue) |
| `queue:processing`                  | LIST | `bot`, `worker`| `worker`        | In-flight (for crash recovery) |
| `queue:dead`                        | LIST | `worker`       | `bot`, `worker` | Permanently failed |
| `job:{id}`                          | HASH | `bot`, `worker`| `bot`, `worker` | Job status, result, retries, timestamps |
| `jobs:index`                        | ZSET | `bot`          | `bot`, `worker` | Job IDs ordered by creation time |
| `jobs:running`                      | ZSET | `worker`       | `bot`, `worker` | Currently running job IDs |
| `jobs:complete`                     | ZSET | `worker`       | `bot`, `worker` | Completed job IDs |
| `chat:{chat_id}:history`            | LIST | `worker`       | `worker`        | Chat conversation turns, trimmed |
| `chat:{chat_id}:model`              | STR  | `bot`          | `worker`        | Per-chat model override |
| `rate:{user_id}`                    | STR  | `bot`, `worker`| `bot`           | Rate-limit sliding window (TTL) |
| `worker:heartbeat`                  | STR  | `worker`       | `bot`           | Worker liveness timestamp (TTL 30s) |
| `pca:latest`                        | STR  | `ml`           | `nodeapi`       | Latest PCA projection (JSON) |
| `pca:components`, `pca:variance`, `pca:eigenvalues`, `pca:mean`, `pca:std` | STR | `ml` | `nodeapi` | PCA artifacts (JSON) |
| `pca:total_variance`                | STR  | `ml`           | `nodeapi`       | Scalar |
| `pca:history`                       | LIST | `ml`           | `nodeapi`       | Latest 100 projections |
| `drift:score`                       | STR  | `ml`           | `nodeapi`       | Drift scalar |
| `drift:classification`              | STR  | `ml`           | `nodeapi`       | "Stable" \| "Moderate" \| "High" \| "Critical" |
| `model:prediction`                  | STR  | `ml`           | `nodeapi`       | Risk label |
| `model:confidence`                  | STR  | `ml`           | `nodeapi`       | Risk confidence (`[0.5, 1.0]`) |
| `risk:latest`                       | STR  | `ml`           | (back-compat)   | Same as `model:prediction` |
| `ml:heartbeat`, `ml:last_run`       | STR  | `ml`           | `nodeapi`       | Worker liveness |

### 7.2 Per-service Redis ACLs

This is the repo's **row-level-security equivalent** for the datastore. (The Postgres RLS rule still applies if a SQL service is ever added.)

| Redis user | Key patterns                                  | Command posture                                |
|------------|-----------------------------------------------|------------------------------------------------|
| `bot`      | `chat:*`, `queue:*`, `job:*`, `rate:*`, `worker:*` | full, minus dangerous commands (`FLUSHDB`, `FLUSHALL`, `KEYS`, `CONFIG`, `SHUTDOWN`, `DEBUG` — renamed to empty at protocol level) |
| `worker`   | `chat:*`, `queue:*`, `job:*`, `worker:*`      | same as `bot`                                  |
| `ml`       | `pca:*`, `drift:*`, `risk:*`, `model:*`, `ml:*` | same as `bot`                                  |
| `nodeapi`  | `pca:*`, `drift:*`, `risk:*`, `model:*`, `ml:heartbeat`, `ml:last_run` | read-only (`+get +hget +hgetall +lrange +zrange +zrevrange +exists +type +ttl +scan -@all`) |
| `default`  | none                                          | `off`                                          |

**Source-of-truth files:**

- `redis/users.acl.template` — checked-in template with `${REDIS_PASSWORD_*}` placeholders.
- `redis/entrypoint.sh` — substitutes placeholders from container env at boot, writes the live ACL to `/usr/local/etc/redis/users.acl` on tmpfs, then `exec redis-server`.
- `redis/redis.conf` — server config (`aclfile /usr/local/etc/redis/users.acl`, dangerous commands renamed).

Adding a new Redis client means adding an ACL user with the narrowest key patterns and command set that works. The new client cannot share an existing user.

---

## 8. Security model

### 8.1 RBAC

Single-operator gate. The Telegram bot accepts commands only from the numeric user id in `ALLOWED_USER`. Every command passes through that check before any business logic runs.

- The gate lives at the top of command dispatch in `core/bot/bot.py`. Any new command must sit behind it.
- Default deny — a message that does not match a known command is not executed. It falls through to the help menu.
- Rate limiting is a second, independent gate (`core/bot/rate_limiter.py`, 10/min/user).
- Every authorization failure is logged with user id, command text, and reason. Tokens, API keys, and secrets are never logged.

### 8.2 Zero trust

- Authenticate every request — Telegram bot token + `ALLOWED_USER` re-check per message.
- The Node API carries no end-user identity — it is an internal read-only projection of ML state, protected by network isolation + Redis ACLs.
- Hand-written input validation per service (no zod, no pydantic).
- No secrets echoed in error responses. Stable, generic error codes.
- **Path containment on model-produced file writes.** The worker applies model-produced file changes into its sandbox: every target path must be normalized, rejected if absolute or escapes the sandbox root, and re-checked against the resolved absolute path. Two layers, because the input is machine-generated.

### 8.3 No keys in the frontend

- `pca-backend` holds zero third-party credentials. It reads from `node-api` over the compose network.
- `core/bot` is a backend service, not a frontend. It holds its own `TELEGRAM_TOKEN` (its identity) and the `AI_GATEWAY_API_KEY` / `GITHUB_TOKEN` it needs to do work, but does not expose any of these to Telegram, the dashboard, or any other surface.
- Build-artifact check: grep `dist/` for secret-shaped strings before shipping a frontend change.

### 8.4 Redis ACLs

See §7.2. `default off` means any client that connects without a username gets nothing. Read-only services are read-only by **command set**, not just by key patterns. Passwords come from env only.

### 8.5 Container posture

Every service runs `read_only: true`, `cap_drop: ALL`, `no-new-privileges: true`, with non-root users. Writable surfaces are tmpfs only. Internal network has `internal: true`. Only `pca-backend` exposes a port (80).

### 8.6 Worker sandbox

- `/sandbox` is the only writable path on the worker (tmpfs, throwaway per restart).
- Model-produced file changes are path-traversal guarded.
- Branches are always `dev-agent/<job-id-prefix>`. **The bot never writes to `main`.**
- `GITHUB_TOKEN` lives in env only and is never written to disk.

Full rationale: `.ai/decisions/security/2026-10-28--no-api-keys-in-frontend-rls-in-database.md`.

---

## 9. Environment variables

Required:

| Var | Purpose |
|---|---|
| `TELEGRAM_TOKEN` | Telegram bot API token (from `@BotFather`) |
| `ALLOWED_USER` | Telegram user ID authorized to use the bot (numeric) |
| `REDIS_PASSWORD_BOT` | Per-service Redis password for the `bot` user |
| `REDIS_PASSWORD_WORKER` | Per-service Redis password for the `worker` user |
| `REDIS_PASSWORD_ML` | Per-service Redis password for the `ml` user |
| `REDIS_PASSWORD_NODEAPI` | Per-service Redis password for the `nodeapi` user |
| `AI_GATEWAY_BASE_URL` | Base URL of the user-owned gateway |
| `AI_GATEWAY_API_KEY` | Bearer token for the gateway |
| `AI_GATEWAY_MODEL` | Default model name (overridable per chat via `/model`) |
| `GITHUB_TOKEN` | Fine-grained PAT with `contents:write` + `pull_requests:write` on target repos |

Optional:

| Var | Default | Purpose |
|---|---|---|
| `DEFAULT_REPO` | (empty) | `owner/repo` used when `/build` is called without a repo |
| `SANDBOX_DIR` | `/sandbox` | Git workspace inside the worker container |
| `CHAT_HISTORY_MAX_TURNS` | `20` | Per-chat history depth |
| `TELEGRAM_MAX_CHARS` | `3800` | Chunk size for Telegram replies |
| `LOG_LEVEL` | `info` | Bot/worker log level |
| `ML_LOG_LEVEL` | `INFO` | ML worker log level |
| `BOT_VERSION` | `1.0.0` | Image tag for `openclaw/bot` |

Generate strong random passwords per service: `openssl rand -hex 32`. Never commit `.env`.

---

## 10. Deployment

```bash
cp .env.example .env
# Fill in required env vars (see §9)

docker compose -f docker-compose.prod.yml up -d --build
```

Stack health:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
docker logs openclaw-bot     # polling, no errors
docker logs openclaw-worker  # "Worker started..."
docker logs openclaw-ml      # "ML worker started (numpy + rules)..."
docker logs pca-backend      # nginx on :80
docker logs node-api         # Listening on 3000
```

Redis ACL check:

```bash
docker exec -it redis redis-cli --user nodeapi --pass "$REDIS_PASSWORD_NODEAPI" ping
docker exec -it redis redis-cli --user ml --pass "$REDIS_PASSWORD_ML" ACL LIST
```

---

## 11. Operational model

- **Bot and worker are stateless** — Redis is the state layer for jobs, chat history, and ML state. A restart loses nothing durable.
- **Worker recovery:** `BRPOPLPUSH` puts in-flight jobs in `queue:processing`; on startup the worker drains `queue:processing` back into `queue:jobs` for re-processing. (Crash recovery is a re-do, not a continue.)
- **ML worker:** loop runs every `ML_WORKER_SLEEP` seconds. Heartbeat is always written. With no data source wired, the loop is dormant by design (no inference to run).
- **Gateway unavailability:** bot and worker retry with exponential backoff (3 attempts, base 0.5s, ±0.25s jitter). After max retries, the job is reported as failed to the user.
- **Image rebuilds:** `docker compose up -d --build` rebuilds only the changed service. The bot and worker share an image; bumping `BOT_VERSION` is the standard way to roll them forward together.

---

## 12. Non-goals

- **Local LLM / Ollama / llama.cpp** — explicitly dropped; the gateway owns inference.
- **`~/ai-gateway`** — user-owned, out of scope for this repo.
- **SQL** — Redis only. Add a database only if a future workflow genuinely needs it (with RLS enabled in the first migration).
- **Multi-tenant SaaS** — single user only.
- **A long-running "learning" ML model** — Phase 4 removed the Keras classifier. Risk classification is rules-based. Adding it back requires a deliberate decision.
- **CI/CD in this repo** — Phase 5. The bot creates `.github/workflows/*.yml` *inside target repos* via the gateway's response, but the workflows that build/deploy this repo itself are not yet shipped.

---

## 13. Roadmap

Implementation status (full plan: `.ai/sessions/llm/2026-10-28-2053--LEAVE-OFF.md`):

- ✅ **Phase 1** — Chat/dictation core. `ai_gateway_client.chat()`, `chat_store.py`, `telegram_sender.py`, `config.py` env knobs.
- ✅ **Phase 2** — Git/PR workflow. `github_client.py`, `/build` + `/chat` + `/pr` commands, `queue_worker.py` rewrite, branch naming `dev-agent/<job-id-prefix>`.
- ✅ **Phase 3** — Container wiring + Redis ACLs. `git` in bot image, `/sandbox` tmpfs on worker, `healthcheck.py` for worker, per-service Redis ACLs (`default off`, `nodeapi` read-only by command set), `docker-compose.prod.yml` rewrite, `.env.example` reorganized.
- ✅ **Phase 4** — ML cleanup + dashboard fixes. Keras + TFLite + `embedding_client.py` removed; `risk_classifier.py` (rules-based, deterministic band-edge confidence); `core/ml/requirements.txt` trimmed to `numpy` + `redis` + `requests`; pca-backend build fixes (`main.tsx`, `index.html`, `global.css` import, `App.tsx` import, nginx `proxy_pass`); optional `risk`/`confidence` on `PcaSummary` so dashboard renders even with empty Redis.
- ⏳ **Phase 5** — CI/CD. `.github/workflows/{ci,deploy,build-pr}.yml` + `.github/actions/docker-build/action.yml`. Write the `lightweight-vertical-to-ai-gateway` decision file (the *why*). Final README roadmap flip + AST/grep verification.

---

## 14. Decision history

Project-level decisions (full text under `.ai/decisions/`):

- `security/2026-10-28--no-api-keys-in-frontend-rls-in-database.md` — the security baseline. No keys in any frontend; RLS if SQL added.
- `simplify/2026-10-24--strip-llm-and-vdb-keep-bot-pca.md` — removed `core/llm` + `core/vdb`; rewired the bot to `~/ai-gateway`.
- `llm/2026-10-19--replace-local-qwen-with-litellm.md` — the LiteLLM gateway decision (the *why* behind the external gateway).
- `llm/2026-10-31--litellm-escalate-interpretation.md` — `LITELLM ESCALATE` / `LITELLM COMPACT` / `LITELLM EXECUTE` are project-internal labels confirming LiteLLM is the gateway tech. Not overrides of plan-first, not new features, not separate modes.
- `skills/2026-10-31--adopt-company-skills-set-adapt-for-repo.md` — the agent skill set adopted from `~/agent-rules/repo-template` and adapted for this repo's stack.

Session history (under `.ai/sessions/`) records the work done in each session.

---

## 15. Glossary

- **`/build`** — Bot command that runs the full git/PR workflow against a target repo.
- **`/chat`** — Bot command that runs pure delegation to `~/ai-gateway` with chat history.
- **`/pr`** — Bot commands for listing, viewing, and merging bot-created PRs.
- **`ALLOWED_USER`** — The numeric Telegram user ID authorized to issue commands to the bot.
- **`ALLOWED_USER` gate** — The RBAC check at the top of every command dispatch path.
- **`AI_GATEWAY_BASE_URL`** — The base URL of the user-owned `~/ai-gateway` (LiteLLM) endpoint.
- **`dev-agent/<job-id-prefix>`** — Branch naming convention for bot-created PRs. The bot never writes to `main`.
- **`LITELLM ESCALATE` / `LITELLM COMPACT` / `LITELLM EXECUTE`** — Project-internal labels confirming the gateway tech (LiteLLM). Not overrides.
- **Plan changes** — The structured `{files: [{path, action, content}]}` response from `~/ai-gateway` to a `/build` instruction.
- **Per-service Redis ACL** — One Redis user per service, scoped by key pattern + (for read-only services) command set. This repo's RLS-equivalent.
- **`SANDBOX_DIR`** — The only writable path on the worker (tmpfs). Default `/sandbox`.
- **Tiny `ml_worker.py`** — The ML loop. Pure numpy + rules. Dormant when no data source is wired.
