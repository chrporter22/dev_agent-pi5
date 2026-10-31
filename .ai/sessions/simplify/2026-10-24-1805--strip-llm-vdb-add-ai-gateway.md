# Strip VDB/LLM proxy, wire bot+worker directly to ai-gateway

- **Date:** 2026-10-24 18:05
- **Developer:** agent
- **Topic:** simplify
- **Status:** complete

## Request

Strip the stack down to just bot + PCA monitoring. Remove `core/vdb` (vector DB/RAG) and `core/llm` (LiteLLM proxy). The telegram bot queues tasks to Redis, worker picks them up and calls the external ai-gateway directly, then sends results back to Telegram. PCA/ML dashboard stack stays as-is.

## What was done

All 10 subtasks complete.

**Removed services:**
- `core/llm/` — entire directory deleted (was the LiteLLM flask proxy)
- `core/vdb/` — entire directory deleted (was FAISS + SQLite + sentence-transformers)
- `bootstrap_vdb.sh` — deleted (stale, referenced removed vdb)
- `core/bot/llm_client.py` — deleted (called the old LLM proxy)
- `core/bot/github_client.py` — deleted (no more GitHub PRs)
- `openclaw_llm_model` and `openclaw_vdb_data` volumes removed from compose

**Modified services:**
- `docker-compose.prod.yml` — 6 services (was 7). Removed `openclaw-llm`, `openclaw-vdb`. Worker now has `outbound_net` + `AI_GATEWAY_*` env. ML no longer has `VDB_HOST`/`VDB_PORT`. Root volumes block removed.
- `core/bot/config.py` — now exports `REDIS_HOST`/`REDIS_PORT`/`REDIS_PASSWORD` (fixes existing ImportError bug) and `AI_GATEWAY_BASE_URL`/`AI_GATEWAY_API_KEY`/`AI_GATEWAY_MODEL`. `LLM_ENDPOINT` removed.
- `core/bot/bot.py` — `chat_id` now tracked in job data so worker can send results back. `/listpr` and `/approvepr` commands removed. Only 4 commands remain: `/build`, `/jobs`, `/job`, `/status`.
- `core/bot/queue_worker.py` — full rewrite. Calls `ai_gateway_client.parse_instruction` instead of `llm_client`. Sends result to Telegram via `send_telegram`. No more GitHub branching/PR logic.
- `core/bot/README.md` — updated for ai-gateway architecture, new commands, new env vars
- `.env.example` — simplified. Removed `LLM_ENDPOINT`, `LLM_VERSION`. Added `AI_GATEWAY_BASE_URL`, `AI_GATEWAY_API_KEY`, `AI_GATEWAY_MODEL`. Fixed `REDIS_URL` hostname to `redis` (was `bot-redis`).
- `install.sh` — full rewrite. Checks `TELEGRAM_TOKEN`, `REDIS_PASSWORD`, `AI_GATEWAY_*`. Builds + starts prod compose. No more LLM proxy steps.
- `AGENTS.md` — services list, known-broken list, deviated-from-standards all updated for new 6-service architecture
- `README.md` — simplified from TODO list to project README

**New file:**
- `core/bot/ai_gateway_client.py` — HTTP client for the external LiteLLM gateway. OpenAI-compatible `/v1/chat/completions`, bearer auth, `response_format: {"type": "json_object"}`, retries with backoff, safe JSON parsing.

**Untouched:**
- `core/ml`, `core/node-api`, `core/pca-backend` — no changes; PCA/monitoring stack preserved
- `core/vdb/tests/` — deleted with the service
- `docker-compose.yml` — left as stale dev file per AGENTS.md rule

## Notable findings

- The `config.py` `REDIS_HOST`/`REDIS_PORT`/`REDIS_PASSWORD` bug was a hard ImportError — the file didn't export what `bot.py` and `queue_worker.py` imported. This is now fixed.
- `core/ml/embedding_client.py` still exists but calls `GET /embeddings` which no longer exists (vdb is gone). The ML pipeline is dormant — it catches the error gracefully. Flagged in AGENTS.md known-broken.
- The worker has both `internal_net` and `outbound_net` — needed for Redis (internal) and Telegram + ai-gateway (external).

## Verification

- `python3 -m py_compile` passes on all 8 bot Python files and all 8 ML Python files
- Git status confirms: 6 new/modified files, 12 deleted files (vdb + llm + bootstrap_vdb.sh + github_client.py + llm_client.py)
- Could not run live compose build/start (no Docker daemon or real env vars on this host)

## Open threads

- User needs to set real `AI_GATEWAY_BASE_URL`, `AI_GATEWAY_API_KEY`, `AI_GATEWAY_MODEL` in `.env` before first run
- Not committed (per user pattern; would go on a `feature/<name>` branch via bot/PR flow)
- `core/pca-backend` still has its known build issues (missing index.html, main.ts vs main.tsx, nginx proxy_pass trailing slash) — untouched per scope
- `core/node-api` still has `redisHelpers.ts` import bug and `REDIS_URL` hostname issue — untouched per scope