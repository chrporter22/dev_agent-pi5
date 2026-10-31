# Telegram dictation + ai-gateway coding workflow + lightweight cleanup

- **Date:** 2026-10-28 20:53 (revised 21:10 after user clarified vision)
- **Developer:** agent
- **Topic:** llm
- **Status:** planning complete + docs written — awaiting explicit "proceed" before implementation

**Companion file**: `.ai/sessions/llm/2026-10-28-2053--LEAVE-OFF.md` is the resume-from-here handoff for the next session (new structure diagram, strict-order next steps, troubleshooting checklist).

## Leave-off point

Read this first when resuming.

**One-line summary**: Repo is being reoriented as a lightweight Telegram vertical to `~/ai-gateway` for AI coding work. Bot creates GitHub branches + PRs directly (gateway only does LLM inference). No local model, no Ollama. Core/ml Keras + TFLite drop. Pca-backend build fixes ship in the same change. PRD + bot README are written and awaiting approval.

**Status**: 🟡 planning, awaiting explicit user "proceed".

**To pick this up**:

1. Read `.ai/decisions/llm/` and `.ai/sessions/llm/` history first (especially the 2026-10-19 litellm swap and 2026-10-24 simplify strip).
2. Read this file's "Revised vision" section.
3. Read "Subtasks" — 14 ordered steps.
4. After approval, work them in order.

**Do not redo**:

- The ai-gateway HTTP client (`core/bot/ai_gateway_client.py` `parse_instruction`) — keep intact, add a sibling `chat()` function instead of rewriting.
- `docker-compose.prod.yml` zero-trust posture on bot/worker — do not weaken to accommodate GitHub push (use token-only env, no new mounts).
- The 6-service topology stays; this change modifies content of 3 services and writes 2 new files in `core/bot/`.
- `core/ml` stays in the stack — only the Keras + TFLite code is removed; PCA/drift/rules-based risk remain.
- `~/ai-gateway` repo is not touched by this work.

---

## Request

User wants the repo to be a lightweight Telegram frontend to `~/ai-gateway` for AI coding work, with:

- Bot creating branches and PRs directly (gateway only does LLM inference)
- No local model, no Ollama, no LLM on the Pi
- Redis cache, SQL only if needed
- Dashboard for analysis
- Plug-in architecture

After clarifying questions, the scope was confirmed.

## Revised vision (confirmed 2026-10-28)

```
Telegram
   ↓
openclaw-bot (commands + dictation dispatch)
   ↓
Redis (queue + cache + chat history)
   ↓
openclaw-worker
   ├── /build: clone repo → call ~/ai-gateway for code → apply → commit → push → open PR → return PR URL
   └── /chat:  call ~/ai-gateway chat → return response text
   ↓
GitHub (PR via GITHUB_TOKEN)
   ↓
Telegram (result reply)

(openclaw-ml → Redis → node-api → pca-backend :80 — unchanged except ML Keras removal)
```

Bot is a thin transport + git worker. No inference in this repo. No local model. No SQL added.

## Decisions confirmed (this session, 2026-10-28)

| # | Topic                  | Decision                                                                                       |
|---|------------------------|------------------------------------------------------------------------------------------------|
| 1 | Dictation command      | Explicit `/chat <text>`. Non-`/` text still falls through to the help menu.                    |
| 2 | Chat history           | Redis-backed, capped at 20 turns per chat. Persists across restarts.                           |
| 3 | Extra commands         | `/clear` wipes history; `/model <name>` sets per-chat model override for `/chat`.              |
| 4 | core/ml Keras + TFLite | **DROPPED.** Keep PCA (numpy), drift detection, and rules-based risk classification.          |
| 5 | GitHub branches + PRs  | **Bot does it directly.** Worker uses git CLI + `GITHUB_TOKEN` in its sandbox repo.            |
| 6 | Context wrapper        | **No** context enrichment in the bot. Raw instruction + chat history only.                     |
| 7 | SQL                    | **Skipped.** Redis only. No new database service.                                              |
| 8 | pca-backend build      | **Fix in this change.** Missing index.html, main.ts → main.tsx, import path, nginx trailing slash. |
| 9 | node-api build         | **Fix in this change** (paired with pca-backend so the dashboard actually works).              |
|10 | LITELLM ESCALATE       | Project-internal label. Use `/model <bigger>` per-chat if escalation is needed.                |
|11 | Bot writes to main     | **NEVER.** Bot only stages (commit + push to branch) and opens PRs. Human merges.              |
|12 | CI in bot PRs          | Bot's `/build` PRs include `.github/workflows/*.yml` for Docker build + unit tests (per gateway response; the gateway is told to include them when adding new code). |
|13 | Embeddings in chat hist| **NOT included.** Redundant — the gateway handles embeddings/RAG. Chat history is plain text.  |
|14 | Dashboard after ML drop| **Still renders.** Dashboard reads PCA/drift/risk from Redis (no model-specific chart). The `confidence` field on `PcaSummary` becomes optional (was Keras-only); risk uses rules. |
|15 | LITELLM COMPACT        | Project-internal label. Keep the LiteLLM/gateway integration compact (thin, no over-engineering). Same status as `LITELLM ESCALATE` — gateway tech is LiteLLM, not an override of plan-first. |
|16 | No keys in frontend    | **Project rule.** Every secret flows through env on a backend service. Bot + dashboard hold zero third-party credentials. Recorded in `.ai/decisions/security/2026-10-28--no-api-keys-in-frontend-rls-in-database.md`. |
|17 | RLS if database added  | **Project rule.** Any future SQL service ships with RLS in its first migration. For Redis (current), per-service ACLs with key-pattern permissions are the target. Same decision file. |

## Subtasks (ordered, after approval)

1. **`core/bot/ai_gateway_client.py`** — add `chat(messages, system)` alongside `parse_instruction()`. Same bearer auth + retry layer, **no** `response_format`. Add chat-specific `SYSTEM_PROMPT` (concise coding-assistant persona).
2. **`core/bot/config.py`** — add `CHAT_HISTORY_MAX_TURNS=20`, `TELEGRAM_MAX_CHARS=3800`, `DEFAULT_REPO` (optional, used by `/build` if no repo given), `SANDBOX_DIR` (git workspace path inside container, e.g. `/sandbox`).
3. **`core/bot/chat_store.py`** *(new)* — `ChatStore.append/history/clear/get_model/set_model`. Backed by Redis. Trim on every append.
4. **`core/bot/telegram_sender.py`** *(new)* — `_chunk_send(chat_id, text)`. Splits on `\n\n`, ≤ `TELEGRAM_MAX_CHARS` per message, tries to keep ``` fenced blocks intact, falls back to hard split if a single block exceeds the limit.
5. **`core/bot/github_client.py`** *(new)* — replaces the version deleted in the 2026-10-24 simplify. Functions: `clone_or_pull(repo, sandbox_dir)`, `create_branch(sandbox_dir, branch_name)`, `commit_all(sandbox_dir, message)`, `push(sandbox_dir, branch_name)`, `open_pr(repo, head, base, title, body)`. Uses `git` CLI via `subprocess` and `requests` for the GitHub REST API (`/repos/{owner}/{repo}/pulls`). `GITHUB_TOKEN` from env.
6. **`core/bot/bot.py`** — wire `/chat`, `/clear`, `/model`. Extend `/build` to accept an optional repo prefix: `/build [owner/repo] <feature>`. If repo omitted, use `DEFAULT_REPO`. RBAC + rate-limit gate every command.
7. **`core/bot/queue_worker.py`** — branch on `job_type` (`"build"` or `"chat"`). Build branch:
   - `github_client.clone_or_pull(DEFAULT_REPO or job['repo'], sandbox)`
   - `github_client.create_branch(sandbox, branch_name)`
   - Call `ai_gateway_client` (new `plan_changes(instruction, repo_context)` helper — see step 8) to get structured code changes
   - Apply changes to sandbox files
   - `github_client.commit_all(sandbox, message)`
   - `github_client.push(sandbox, branch_name)`
   - `github_client.open_pr(repo, branch_name, base, title, body)`
   - Send PR URL back to Telegram
   - On git error, send error to Telegram (don't dead-letter — user can retry)
   Chat branch: load history → call `chat()` → append both turns → chunk-send reply.
8. **`core/bot/ai_gateway_client.py`** *(continued)* — add `plan_changes(instruction, repo_context)` returning structured JSON `{files: [{path, action: "create"|"modify"|"delete", content}]}`. Uses `response_format: {"type": "json_object"}` (kept for build jobs; only chat drops it). `SYSTEM_PROMPT` updated to ask for this shape AND to include `.github/workflows/*.yml` for Docker build + unit tests when adding new code.
9. **`core/bot/Dockerfile`** — add `git` to the system packages (or use `python:3.11-slim` already there? — verify). Add a non-root `sandbox` working dir with tmpfs mount from compose.
10. **`docker-compose.prod.yml`** — add `SANDBOX_DIR=/sandbox` env to `openclaw-worker`. Add tmpfs mount `/sandbox` (writable). Add `GITHUB_TOKEN` env forwarding from `.env`. Keep `read_only: true` on root FS — only `/sandbox` is writable via tmpfs.
11. **`.env.example`** — add `GITHUB_TOKEN=ghp_...`, `DEFAULT_REPO=owner/repo` (optional), `SANDBOX_DIR=/sandbox`.
12. **`core/ml/` cleanup**:
    - Delete `core/ml/model.py` (Keras model + TFLite export)
    - Strip model training + TFLite export from `core/ml/training.py` if present
    - Delete or simplify `core/ml/embedding_client.py` (no vdb)
    - `core/ml/pca.py`, `core/ml/drift.py`, `core/ml/risk.py` (rules) — keep
    - `core/ml/main.py` — remove model-training call, keep PCA + drift + rules loop
    - `core/ml/README.md` — update to reflect no-model architecture
13. **`core/pca-backend/` build fixes**:
    - Rename `src/main.ts` → `src/main.tsx` (it contains JSX)
    - Fix `App.tsx` line-broken `import Dashboard\nfrom "./pages/Dashboard"` (add the missing parts: complete import on one line, missing semicolon — actually the file says "no semicolons" per AGENTS.md, so just fix the line break)
    - Fix import path `./styles/globals.css` → `./styles/global.css`
    - Create missing `index.html` at `core/pca-backend/index.html` (Vite expects it at root)
    - `nginx.conf` — remove trailing slash on `proxy_pass http://node-api:3000/;` (keep the path prefix)
14. **`core/node-api/` build fixes**:
    - Rename `src/utils/redisHelpers.ts` → `src/utils/redisHelper.ts` (and update the import in `src/routes/ml.ts`)
    - Replace `REDIS_URL` reads with `REDIS_HOST` + `REDIS_PORT` reads in `src/redis/client.ts`
15. **Documentation**:
    - **Root `README.md`** — full rewrite as PRD. See "PRD outline" below.
    - **`core/bot/README.md`** — full rewrite for the new bot + worker workflow (build/PR + chat + commands + env vars).
    - **`.ai/decisions/llm/2026-10-28--lightweight-vertical-to-ai-gateway.md`** *(new)* — record this scope decision (the *why*).
16. **Verification**:
    - `python3 -m py_compile` on every touched `.py` in `core/bot/` and `core/ml/`.
    - `npm run build` in `core/pca-backend` and `core/node-api`.
    - AST sanity check on `ai_gateway_client` (functions: `parse_instruction`, `chat`, `plan_changes`).
    - Confirm `parse_instruction` signature unchanged (back-compat).
    - Grep for stray imports of removed symbols.
17. **Finalize** this session file with verification report.

## PRD outline (root README.md rewrite)

- **Overview**: One-paragraph vision — thin Telegram frontend to `~/ai-gateway` for AI coding work on a Pi 5.
- **Architecture**: ASCII diagram of Telegram → bot → Redis → worker → gateway → git/PR → Telegram reply. Plus the analytics chain.
- **Services** (6, unchanged topology): bot, worker, redis, ml, node-api, pca-backend. One sentence each.
- **Bot commands**: `/build [repo] <feature>`, `/chat <text>`, `/jobs`, `/job <id>`, `/status`, `/clear`, `/model <name>`.
- **Build flow**: clone repo → branch → call gateway → apply → commit → push → PR → Telegram reply with PR URL.
- **Chat flow**: load history → call gateway chat → append turns → chunk-send reply.
- **Security posture**: read-only containers, cap_drop ALL, no-new-privileges, GITHUB_TOKEN env-only, SANDBOX_DIR tmpfs only.
- **Environment**: list of required + optional vars.
- **Out of scope**: local LLM/Ollama (gateway owns inference), GitHub Action definitions (live in target repos), `~/ai-gateway` repo (user-owned).

## Open threads

- User wires `TELEGRAM_TOKEN`, `ALLOWED_USER`, `REDIS_PASSWORD`, `AI_GATEWAY_*`, `GITHUB_TOKEN`, optional `DEFAULT_REPO` in `.env`.
- `GITHUB_TOKEN` needs `repo` scope (push + PR).
- Not committed (per repo pattern).
- `~/ai-gateway` repo changes (if any, to expose the build endpoint the worker will call) — out of scope here.

## Verification (planned)

- `python3 -m py_compile` on `core/bot/{ai_gateway_client,bot,queue_worker,chat_store,telegram_sender,github_client,config}.py`.
- `python3 -m py_compile` on `core/ml/{pca,drift,risk,main,config}.py` (after model removal).
- `npm run build` in `core/pca-backend` and `core/node-api`.
- AST check on `ai_gateway_client` and `queue_worker`.
- Grep for stale refs (`Keras|TFLite|tflite|model\.keras|embedding_client`).
- Live compose build/test — needs Docker daemon + real env vars (cannot run on host).
