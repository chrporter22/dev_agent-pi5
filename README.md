# DEV AGENT Pi

Lightweight Telegram frontend to a user-owned AI gateway, deployed on a Raspberry Pi 5 (ARM64, 16GB, Arch Linux). This repo does no local inference. The external `~/ai-gateway` provides all LLM capability; this repo is a thin transport plus a git worker that opens pull requests on the user's behalf.

```
Telegram
   |
   v
openclaw-bot (commands + dictation, RBAC + rate-limited)
   |
   v
Redis (per-service ACLs: queue + cache + chat history + ML state)
   |
   v
openclaw-worker
   |-- /build:  clone repo -> call ~/ai-gateway -> apply code -> commit -> push -> open PR
   '-- /chat:   call ~/ai-gateway chat -> reply

Analytics chain (dormant until a data source is wired):
openclaw-ml (PCA, drift, rules-based risk) -> Redis -> node-api -> pca-backend (nginx :80)
```

---

## What this is

A zero-trust, fully containerized Telegram coding interface. The bot receives natural-language instructions, the worker delegates LLM work to `~/ai-gateway`, and the worker performs the resulting git actions directly so pull requests land in the user's repositories for review.

**Two workflows**, one bot:

- **`/build [owner/repo] <feature>`** — full coding workflow. Clones the target repo into a sandbox, asks the gateway for structured code changes, applies them, commits, pushes a branch, and opens a PR. Returns the PR URL to Telegram.
- **`/chat <text>`** — dictation. Free-text conversation with the gateway. Maintains per-chat history in Redis so follow-ups have context.

Both routes go through the same `~/ai-gateway`; the difference is whether git work happens.

## What this is not

- **Not a local LLM runner.** No model weights on the Pi. No Ollama. No llama.cpp. The gateway owns inference.
- **Not a coding agent in this repo.** The gateway is the agent. This repo transports the request and performs the git actions.
- **Not multi-tenant.** Single user (enforced by `ALLOWED_USER`). No Firebase, no org keys, no SaaS layer.
- **Not a database.** Redis only. No SQL is added; long-term state is the user's responsibility.

---

## Services

Six containers. Internal network is closed. Only `pca-backend` publishes a port. Each service authenticates to Redis as its own user with its own key-pattern scope.

| Service            | Role                                                              | Network             | Redis user |
|--------------------|-------------------------------------------------------------------|---------------------|------------|
| `redis`            | Job queue, chat history, ML state, cache (per-service ACLs)       | internal            | n/a        |
| `openclaw-bot`     | Telegram polling, command parsing, RBAC, rate limit, job queuing  | internal + outbound | `bot`      |
| `openclaw-worker`  | Queue consumer; `/build` = git + gateway + PR; `/chat` = gateway | internal + outbound | `worker`   |
| `openclaw-ml`      | Background analytics: PCA (numpy), drift, rules-based risk       | internal            | `ml`       |
| `node-api`         | Read-only Express layer serving ML Redis state                    | internal            | `nodeapi`  |
| `pca-backend`      | React + Tailwind dashboard behind nginx                           | internal + outbound (only public port :80) | none       |

`openclaw-ml` runs pure-numpy PCA and statistical drift detection. **No neural network.** No model weights loaded by any service.

---

## Quick start

```bash
# 1. Copy the env template
cp .env.example .env

# 2. Fill in the secrets
#    Required: TELEGRAM_TOKEN, ALLOWED_USER,
#              REDIS_PASSWORD_{BOT,WORKER,ML,NODEAPI},
#              AI_GATEWAY_BASE_URL, AI_GATEWAY_API_KEY, AI_GATEWAY_MODEL,
#              GITHUB_TOKEN

# 3. Build and start
docker compose -f docker-compose.prod.yml up -d --build

# 4. Verify
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
docker logs openclaw-bot     # should poll Telegram with no errors
docker logs openclaw-worker  # should show "Worker started..."
```

First-run check in Telegram:

```
/status                              # queue depth = 0, redis online
/build myorg/myrepo add CSV export   # expect: "Job <id> — PR opened: <url>"
/chat hello                          # expect a reply from the gateway
```

The dashboard is at `http://<pi-ip>/`. PCA / drift / risk panels populate after `openclaw-ml`'s first loop (~1 minute) once a data source is wired.

---

## Bot commands

Owner-only (enforced via `ALLOWED_USER`). Rate limit: 10 commands/minute per user.

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

Anything else gets the help menu.

---

## Build flow (`/build`)

1. User sends `/build myorg/myrepo add CSV export to /reports`.
2. `openclaw-bot` queues a `build` job to Redis with `chat_id`, `repo`, `instruction`.
3. `openclaw-worker` picks the job up.
4. Worker clones `myorg/myrepo` into the sandbox (`SANDBOX_DIR=/sandbox`, tmpfs-backed).
5. Worker creates a branch `dev-agent/<job-id-prefix>`.
6. Worker calls `~/ai-gateway` with the instruction; gateway returns structured code changes (`{files: [{path, action, content}]}`).
7. Worker applies the changes in the sandbox (path-traversal guarded).
8. Worker commits and pushes the branch.
9. Worker opens a PR via GitHub REST API using `GITHUB_TOKEN`.
10. Worker replies to Telegram: `Job abc12345 — PR opened: https://github.com/myorg/myrepo/pull/42`.

Failures are reported to Telegram with the error. No retry on `/build` git failures — the user decides whether to retry after fixing.

## Chat flow (`/chat`)

1. User sends `/chat how should I structure the migration?`.
2. Bot queues a `chat` job with `chat_id` and `instruction`.
3. Worker loads `chat:{chat_id}:history` (last 20 turns) from Redis.
4. Worker calls `~/ai-gateway` chat completions with system prompt + history + new user turn.
5. Worker appends both turns to history (trimmed to 20).
6. Worker chunks the response (≤ 3800 chars/message, splits on `\n\n`) and sends to Telegram.

---

## Environment

Required:

- `TELEGRAM_TOKEN` — Telegram bot API token (from `@BotFather`).
- `ALLOWED_USER` — Telegram user ID authorized to use the bot (numeric, from `@userinfobot`).
- `REDIS_PASSWORD_BOT`, `REDIS_PASSWORD_WORKER`, `REDIS_PASSWORD_ML`, `REDIS_PASSWORD_NODEAPI` — one per Redis ACL user. Generate strong random per-service values.
- `AI_GATEWAY_BASE_URL` — base URL of the user-owned gateway (e.g. `https://ai-gateway.example.com`).
- `AI_GATEWAY_API_KEY` — bearer token for the gateway.
- `AI_GATEWAY_MODEL` — default model name (e.g. `gpt-4o-mini`). Overridable per-chat via `/model`.
- `GITHUB_TOKEN` — fine-grained PAT with `contents: write` and `pull-requests: write` on target repos.

Optional:

- `DEFAULT_REPO` — `owner/repo`. Used when `/build` is called without a repo argument.
- `SANDBOX_DIR` — git workspace path inside the worker container (default `/sandbox`).
- `CHAT_HISTORY_MAX_TURNS` — per-chat history depth (default 20).
- `TELEGRAM_MAX_CHARS` — chunk size for Telegram replies (default 3800).
- `LOG_LEVEL` / `ML_LOG_LEVEL` — `info` (default) or `debug` / `INFO`.
- `BOT_VERSION` — image tag for `openclaw/bot` (default `1.0.0`).

---

## Security posture

This is a zero-trust, fully containerized stack. Each layer enforces access on its own; if one layer fails, the next still denies.

**Container hardening (every service):**

- `read_only: true` on root FS; tmpfs for writable surfaces only.
- `cap_drop: ALL`, `security_opt: no-new-privileges: true`.
- Non-root users (`botuser`, `mluser`, `nginx`).
- `pids_limit` and `mem_limit` per service.
- Internal network (`internal: true`); only `pca-backend` exposes `:80`.
- No docker.sock, no host mounts, no privileged flags.

**Secrets handling:**

- All secrets flow through env on a backend service.
- **No API keys in any frontend.** The Telegram bot (input surface) and the PCA dashboard (output surface) hold zero third-party credentials. Only the bot's own `TELEGRAM_TOKEN` (its identity) is held by the bot.
- `.env` is gitignored; `.env.example` carries placeholders.

**Redis (the datastore):**

- **Per-service ACLs** (Redis 7 user+key-pattern permissions) — the equivalent of database row-level security for this repo's stack.
- `default` user is `off` — a client that connects without a username gets nothing.
- Read-only services (`nodeapi`) are read-only by **command set**, not just key patterns — defense in depth.
- Passwords come from env only. The substituted ACL lives on a tmpfs inside the redis container so it does not persist across restarts.

| Redis user | Key patterns                                  | Command posture                                |
|------------|-----------------------------------------------|------------------------------------------------|
| `bot`      | `chat:*`, `queue:*`, `job:*`, `rate:*`, `worker:*` | full, minus dangerous commands               |
| `worker`   | `chat:*`, `queue:*`, `job:*`, `worker:*`      | full, minus dangerous commands                 |
| `ml`       | `pca:*`, `drift:*`, `risk:*`, `model:*`, `ml:*` | full, minus dangerous commands               |
| `nodeapi`  | `pca:*`, `drift:*`, `risk:*`, `model:*`, `ml:heartbeat`, `ml:last_run` | read-only (`+get +hget +hgetall +lrange +zrange +zrevrange +exists +type +ttl +scan -@all`) |
| `default`  | none                                          | `off`                                          |

**Worker sandbox:**

- `/sandbox` is the only writable path on the worker (tmpfs).
- Model-produced file changes are path-traversal guarded (reject `..`, absolute paths, or paths that resolve outside the sandbox).
- Branch is always `dev-agent/<job-id-prefix>`. **The bot never writes to `main`.**

**Outbound access:**

- `openclaw-bot`: Telegram API only.
- `openclaw-worker`: Telegram API (for replies), `~/ai-gateway` (LLM calls), GitHub REST API (for PRs).
- `openclaw-ml`: no outbound (no data source currently wired).
- `pca-backend`: compose-network to `node-api` only.

Full rationale: `.ai/decisions/security/2026-10-28--no-api-keys-in-frontend-rls-in-database.md` and `.ai/decisions/skills/2026-10-31--adopt-company-skills-set-adapt-for-repo.md` (for the adapted Redis-ACL section).

---

## Verification

```bash
# Stack health
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Per-service
docker logs openclaw-bot     # polling, no errors
docker logs openclaw-worker  # "Worker started..."
docker logs openclaw-ml      # "ML worker started (numpy + rules)..." (heartbeat ticks even without data)
docker logs pca-backend      # nginx on :80
docker logs node-api         # "Listening on 3000"

# Redis ACLs in effect
docker exec -it redis redis-cli --user nodeapi --pass "$REDIS_PASSWORD_NODEAPI" ping
docker exec -it redis redis-cli --user ml --pass "$REDIS_PASSWORD_ML" ACL LIST
```

In Telegram:

```
/status                          # queue depth = 0, redis online
/build myorg/myrepo add README   # expect: "Job <id> — PR opened: <url>"
/jobs                            # see the build job
/job <id>                        # see the PR URL
/chat thanks                     # expect a reply
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Bot silent in Telegram | `ALLOWED_USER` mismatch | Verify your numeric Telegram user ID (`@userinfobot`) |
| Worker can't reach gateway | DNS / `outbound_net` blocked / `AI_GATEWAY_API_KEY` rejected | Check `docker logs openclaw-worker` for the error |
| `git push` rejected | `GITHUB_TOKEN` missing `contents:write`, or not authorized on target repo | Regenerate fine-grained PAT with the right scopes |
| PR open rejected | Token missing `pull_requests:write`, branch protection blocks the bot, or repo archived | Loosen branch protection for bot branches; check token scopes |
| Dashboard blank | `openclaw-ml` hasn't run yet, or `node-api` can't reach Redis | Check `REDIS_HOST`/`REDIS_PORT`; `node-api` uses the `nodeapi` user |
| `/chat` returns nothing | `CHAT_HISTORY_MAX_TURNS=0` would break it | Must be ≥ 2 |
| Redis ACL errors at startup | Password substitution failed in `entrypoint.sh` | Confirm all `REDIS_PASSWORD_*` env vars are set |

---

## Project structure

```
dev_agent-pi5/
|-- README.md                          # this file
|-- PRD.md                             # product requirements (full spec)
|-- AGENTS.md                          # agent rules (planning, single-agent, memory)
|-- docker-compose.prod.yml            # authoritative: 6 services, zero-trust
|-- docker-compose.yml                 # dev-only, stale (see AGENTS.md)
|-- .env.example                       # placeholder env (commit this; .env is gitignored)
|-- install.sh                         # bootstrap (stale; see AGENTS.md)
|-- core/
|   |-- bot/                           # TELEGRAM FRONTEND (bot + worker share image)
|   |   |-- bot.py                     # polling + command dispatch + RBAC
|   |   |-- queue_worker.py            # build|chat dispatch
|   |   |-- ai_gateway_client.py       # parse_instruction + chat + plan_changes
|   |   |-- chat_store.py              # Redis-backed history + per-chat model
|   |   |-- telegram_sender.py         # _chunk_send
|   |   |-- github_client.py           # git CLI + GitHub REST
|   |   |-- healthcheck.py             # TCP check on AI_GATEWAY_BASE_URL
|   |   |-- rate_limiter.py            # 10 cmd/min/user
|   |   |-- config.py                  # env reads + defaults
|   |   |-- Dockerfile                 # python:3.11-slim + git + non-root
|   |   '-- README.md
|   |-- ml/                            # ANALYTICS — numpy/stats, no model
|   |   |-- pca_engine.py              # top-5 components via numpy eigh
|   |   |-- drift_detector.py          # centroid + variance shift
|   |   |-- risk_classifier.py         # rules-based (was Keras)
|   |   |-- ml_worker.py               # loop: PCA -> drift -> risk -> Redis
|   |   |-- config.py
|   |   |-- Dockerfile
|   |   '-- README.md
|   |-- node-api/                      # READ-ONLY EXPRESS OVER REDIS
|   |   |-- src/redis/client.ts        # per-field config (REDIS_HOST/PORT/USER/PASSWORD)
|   |   |-- src/utils/redisHelper.ts
|   |   |-- src/routes/ml.ts           # /api/ml/{pca,drift,risk,history}
|   |   '-- ...
|   '-- pca-backend/                   # REACT DASHBOARD (only public ingress)
|       |-- index.html
|       |-- src/main.tsx
|       |-- src/App.tsx
|       |-- src/styles/global.css
|       |-- nginx.conf
|       '-- ...
|-- redis/
|   |-- redis.conf                     # bind, appendonly off, aclfile, dangerous commands renamed
|   |-- users.acl.template             # 4 users + default off; ${PASSWORD_*} placeholders
|   '-- entrypoint.sh                  # sed-substitute passwords from env, exec redis-server
'-- .ai/
    |-- decisions/                     # business decision history
    |   |-- security/2026-10-28--no-api-keys-in-frontend-rls-in-database.md
    |   |-- simplify/2026-10-24--strip-llm-and-vdb-keep-bot-pca.md
    |   |-- llm/2026-10-19--replace-local-qwen-with-litellm.md
    |   |-- llm/2026-10-31--litellm-escalate-interpretation.md
    |   '-- skills/2026-10-31--adopt-company-skills-set-adapt-for-repo.md
    |-- sessions/                      # AI work history (one file per session)
    |   |-- llm/...
    |   '-- simplify/...
    '-- README.md
.claude/
'-- skills/                            # agent skills (see below)
    |-- docker-testing/
    |-- security-rbac-zero-trust/
    |-- eda-econometrics-numpy/
    |-- no-agent-push/
    |-- pii-redaction/
    |-- repo-index/
    |-- data-science/                  # numpy + rules-only (this repo's stack)
    |-- repo-memory/
    '-- rules-site/
```

---

## Agent skills

`.claude/skills/` is the skill set the agent loads per task. Adopted from the company template (`~/agent-rules/repo-template`) and adapted for this repo:

| Skill | What it covers |
|---|---|
| `docker-testing` | Run all builds/tests/lint inside Docker; fallback ladder for hosts without a daemon |
| `security-rbac-zero-trust` | RBAC, zero-trust, no keys in frontend, **per-service Redis ACLs** (this repo's RLS equivalent) |
| `eda-econometrics-numpy` | Numpy-only PCA + statistical drift (this repo's ML stack) |
| `no-agent-push` | The agent never pushes; the human user is the only actor that writes to a remote |
| `pii-redaction` | Mask secrets/PII in `.ai/` memory before writing |
| `repo-index` | Build, maintain, and query `.ai/index/` (skill installed; index not yet built — opt-in) |
| `data-science` | numpy-only PCA + drift + rules-based risk, served via Redis to a Node/TS stack (this repo's actual stack) |
| `repo-memory` | Read/update `.ai/sessions/` and `.ai/decisions/` |
| `rules-site` | Static HTML viewer for AGENTS.md / CLAUDE.md / .ai memory |

Adapted where they conflicted with this repo's stack. Full rationale: `.ai/decisions/skills/2026-10-31--adopt-company-skills-set-adapt-for-repo.md`.

---

## Roadmap

Implementation status (full plan: `.ai/sessions/llm/2026-10-28-2053--LEAVE-OFF.md`):

- ✅ **Phase 1** — Chat/dictation core. `ai_gateway_client.chat()`, `chat_store.py`, `telegram_sender.py`.
- ✅ **Phase 2** — Git / PR workflow. `github_client.py`, `/build` + `/chat` + `/pr` commands, `queue_worker.py` rewrite.
- ✅ **Phase 3** — Container wiring + Redis ACLs. `git` in bot image, `/sandbox` tmpfs, per-service Redis ACLs.
- ✅ **Phase 4** — ML cleanup + dashboard fixes. Keras + TFLite removed; `risk_classifier.py` (rules-based); pca-backend build fixes (main.tsx, index.html, css rename, nginx).
- ⏳ **Phase 5** — CI/CD. `.github/workflows/{ci,deploy,build-pr}.yml` + `.github/actions/docker-build/action.yml`; write the `lightweight-vertical-to-ai-gateway` decision file.

---

## Development

Each service has its own Dockerfile + dependencies. There is **no repo-wide lint/format/test command**. Verify per service, per AGENTS.md:

```bash
# core/node-api
cd core/node-api && npm run build         # tsc

# core/pca-backend
cd core/pca-backend && npm run build      # tsc + vite

# core/bot and core/ml
python3 -m py_compile core/bot/*.py core/ml/*.py

# docker-compose.prod.yml
python3 -c "import yaml; yaml.safe_load(open('docker-compose.prod.yml'))"
```

`core/pca-backend`'s `npm run lint` is declared but broken (eslint not in devDependencies and no config file exists). Do not treat its failure as a regression.

---

## Out of scope

- **`~/ai-gateway` repo** — user-owned, not modified by this project.
- **GitHub Actions definitions in this repo** — the bot creates `.github/workflows/*.yml` *inside target repos* (via the gateway's response), but the actions repo itself is not part of this project.
- **Local LLM / Ollama / llama.cpp** — explicitly dropped; the gateway owns inference.
- **SQL** — Redis only. Add a database only if a future workflow genuinely needs it (with RLS enabled in the first migration).
- **Multi-tenant SaaS** — single user only.
- **Phase 5 CI** — pending; roadmap above.
