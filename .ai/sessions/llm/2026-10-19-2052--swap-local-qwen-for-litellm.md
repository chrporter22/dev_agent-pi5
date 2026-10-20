# Swap local Qwen for external LiteLLM gateway

- **Date:** 2026-10-19 20:52 (work), 21:00 (finalized)
- **Developer:** agent
- **Topic:** llm
- **Status:** code complete, uncommitted, awaiting user to set gateway credentials

---

## Leave-off point — read this first when resuming

**One-line summary**: `core/llm` is now a thin stateless Flask proxy that forwards `POST /parse` from `core/bot` to an external LiteLLM gateway. The local Qwen2-1.5B + llama.cpp stack was removed entirely. All 14 planned subtasks are done and verified; nothing was committed.

**Status**: 🟡 code ready, blocked on user wiring.

**To pick this up**:

1. Read `.ai/decisions/llm/2026-10-19--replace-local-qwen-with-litellm.md` first — it has the *why* (the architectural intent).
2. Read the **File status** table below — every touched file's final state.
3. Set `AI_GATEWAY_BASE_URL`, `AI_GATEWAY_API_KEY`, `AI_GATEWAY_MODEL` in `.env` (see `.env.example` for placeholders). The proxy refuses to start without these.
4. From the host, `docker compose -f docker-compose.prod.yml up -d --build openclaw-llm`, then verify with `curl http://openclaw-llm:8080/health` (reachable only from inside the docker network — exec into `openclaw-bot` or `openclaw-worker` to test `POST /parse`).

**Do not redo**:

- The llama.cpp / Qwen model download path is intentionally gone. `install.sh` no longer downloads anything.
- `core/bot` consumer code is unchanged. It still talks to `LLM_ENDPOINT=http://openclaw-llm:8080`. Do not re-introduce `LLM_HOST` / `LLM_PORT` env on `openclaw-worker` (they were dead and were removed).
- `core/llm/config.py` validates required env vars at startup. Don't make it silently tolerant.
- The `openclaw_llm_model` Docker volume is still declared in compose (for back-compat with external docs) but no service mounts it. Don't re-mount it.
- `dns: []` on `openclaw-llm` is intentionally removed — the gateway hostname must resolve.

**If something looks wrong, check here first**:

- Proxy won't start → almost certainly missing `AI_GATEWAY_*` in `.env`. `core/llm/config.py` exits with a clear message.
- `POST /parse` returns 502 → upstream gateway unreachable, bad key, or model name wrong. Check gunicorn logs.
- `POST /parse` returns 504 → upstream timed out. `LLM_TIMEOUT_SECONDS` defaults to 30; tune via env.
- `core/bot` retries look multiplicative with proxy retries → see Notable findings; tune `LLM_MAX_RETRIES` or `core/bot/llm_client.py` if latency becomes a problem.

---

## File status (final state of every file touched)

| File                                       | Change                                                              | State      |
|--------------------------------------------|---------------------------------------------------------------------|------------|
| `.env.example`                             | `LLM_VOLUME` block → `AI_GATEWAY_*` placeholders                    | modified   |
| `docker-compose.prod.yml` (`openclaw-llm`) | gained `outbound_net` + env_file; lost `dns: []` + 8GB cap + model volume | modified |
| `docker-compose.prod.yml` (`openclaw-worker`) | dropped unused `LLM_HOST`/`LLM_PORT` env                         | modified   |
| `core/llm/Dockerfile`                      | `python:3.12-slim` + non-root `llmuser` + gunicorn; no llama.cpp    | modified   |
| `core/llm/requirements.txt`                | added `gunicorn==21.2.0`, `requests==2.31.0`                        | modified   |
| `core/llm/config.py`                       | NEW. Module-level env reads, validates required vars at import     | new        |
| `core/llm/app.py`                          | Full rewrite: OpenAI-compat proxy, `POST /parse`, `/health`         | modified   |
| `core/llm/llm-server/`                     | Deleted (was dead; removed llama.cpp start script)                  | deleted    |
| `core/llm/README.md`                       | Full rewrite for proxy role                                          | modified   |
| `AGENTS.md` (line 138 + known-broken list) | `core/llm` description updated; port-8081 mismatch entry removed    | modified   |
| `README.md` (lines 113, 129)               | Local Qwen wording → external LiteLLM gateway                       | modified   |
| `install.sh`                               | Dead Qwen download block removed; `AI_GATEWAY_*` env check added    | modified   |
| `.ai/decisions/llm/2026-10-19--replace-local-qwen-with-litellm.md` | NEW. Decision record (the *why*)                     | new        |
| `.ai/sessions/llm/2026-10-19-2052--swap-local-qwen-for-litellm.md`  | This file. Session record (the *what* and *how*)     | new        |

**Verification done** (host-side ceiling only):

- `python3 -m py_compile core/llm/app.py core/llm/config.py` → OK.
- `yaml.safe_load(docker-compose.prod.yml)` parses; `openclaw-llm` networks = `[internal_net, outbound_net]`, mem_limit = `512m`, env_file = `.env`, env = `AI_GATEWAY_*` only, no `dns:`, no model volume.
- AST inspection: routes `POST /parse`, `GET /health` registered.
- `bash -n install.sh` → OK.
- Grep for stale refs (`llm-server|llama\.cpp|qwen|LLAMA_|MODEL_FILENAME|MODEL_URL|MODEL_SHA256`) → only hits in this file, the decision file, and `core/llm/README.md` "What was removed" section. All intentional.
- Could not run live Flask tests on the host: `requests` / `flask` are container-only deps per AGENTS.md. Live testing must happen inside the running container.

**Verification still owed**:

- Live `docker compose up -d --build openclaw-llm` — needs Docker daemon + real `AI_GATEWAY_*` values.
- Live `POST /parse` round-trip from `openclaw-bot` → proxy → external gateway.

---

## Request (original, for reference)

User asked to "update this repo to connect to ai-gateway endpoint plan integration", then clarified in two follow-ups:

- `~/ai-gateway` is a separate user-owned repo; this repo just wires to it.
- Local Qwen2-1.5B is not powerful enough; replace it with the external LiteLLM gateway.
- Security provisions still apply.
- Don't touch `~/ai-gateway` — user wires the API later (placeholders only).
- `LITELLM EXECUTE` / `LITELLM ESCALATE` appeared as suffix tokens; treated as project-internal labels (LiteLLM is the chosen tech), not as overrides of the mandatory plan-first rule.

## Decisions confirmed before implementation

- Gateway: LiteLLM proxy (OpenAI-compatible `/v1/chat/completions`).
- Consumer: `core/bot` only, called via a thin proxy in `core/llm`.
- Strategy: Replace local entirely (drop llama.cpp + Qwen from this repo).
- Call path: `core/bot` → `LLM_ENDPOINT=http://openclaw-llm:8080` → external LiteLLM. `core/llm` is the only service with egress.
- Auth: Bearer API key in env.
- JSON contract: `response_format: {"type": "json_object"}` + hand-written validation (matches repo style, no zod).
- Compose fate: keep `core/llm` service, repurpose as proxy. Drop 8 GB mem cap, model volume mount, `dns: []`, `user:` directive. Add `outbound_net`, `env_file`, env forwarding.
- Out of scope: `~/ai-gateway` repo, `core/bot` consumer code, commit.

## What was done

All 14 planned subtasks completed:

1. `.env.example` — replaced `LLM_VOLUME` block with `AI_GATEWAY_BASE_URL`, `AI_GATEWAY_API_KEY`, `AI_GATEWAY_MODEL` placeholders; kept `LLM_ENDPOINT`.
2. `docker-compose.prod.yml` → `openclaw-llm` — added `outbound_net`, `env_file: .env`, env forwarding; dropped `dns: []`, model volume mount, 8 GB mem cap, `user:`, `memswap_limit`. All zero-trust primitives preserved.
3. `docker-compose.prod.yml` → `openclaw-worker` — dropped unused `LLM_HOST`/`LLM_PORT` env (worker reads `LLM_ENDPOINT` from `.env`).
4. `core/llm/Dockerfile` — replaced `ubuntu:22.04` + llama.cpp build with `python:3.12-slim` + non-root `llmuser`. Runs gunicorn (2 workers).
5. `core/llm/requirements.txt` — added `gunicorn==21.2.0`, `requests==2.31.0`; kept `flask==2.3.3`.
6. `core/llm/config.py` (NEW) — module-level env reads; refuses to start without `AI_GATEWAY_BASE_URL` / `AI_GATEWAY_API_KEY` / `AI_GATEWAY_MODEL`. Validates URL scheme.
7. `core/llm/app.py` — full rewrite. Keeps Flask + `POST /parse` contract for `core/bot`. Sends OpenAI-compat request to `${AI_GATEWAY_BASE_URL}${LLM_GATEWAY_CHAT_PATH}` with bearer auth and `response_format: {"type": "json_object"}`. Hand-written response validation. Retries with backoff. Maps errors to 502 / 504. Adds `GET /health`. Banner style preserved.
8. Deleted `core/llm/llm-server/` (containing `start-llm.sh`). Clears the known-broken port-8081-vs-8080 mismatch flagged in AGENTS.md as a direct side effect of the rewrite.
9. `core/llm/README.md` — full rewrite for the new role (thin proxy, external gateway). Documents new env vars, security posture, what was removed.
10. `AGENTS.md` line 138 — `core/llm` description updated to reflect the proxy role.
11. `README.md` lines 113 and 129 — replaced "Local Qwen2-1.5B LLM inference (llama.cpp)" and the architecture arrow label.
12. `.ai/decisions/llm/2026-10-19--replace-local-qwen-with-litellm.md` (decision file).
13. This session file.
14. Verify: `python3 -m py_compile core/llm/app.py core/llm/config.py` OK; `yaml.safe_load(docker-compose.prod.yml)` parses; `openclaw-llm` networks = `internal_net + outbound_net`, mem_limit = `512m`, env_file = `.env`, env = `AI_GATEWAY_*` only; grep for stale `llm-server|llama\.cpp|qwen|LLAMA_|MODEL_FILENAME|MODEL_URL|MODEL_SHA256` across all relevant files returns hits only in the new memory files (intentional documentation of what changed) and the new README's "what was removed" section.

## Side fixes bundled into this change (called out in plan)

- `install.sh` — replaced the dead Qwen model-download section (lines 4-8, 41-78, 123-124) with an `AI_GATEWAY_*` env validation step. Same trigger as the original ("rebuild app instead of local Qwen"), not an unrelated fix. `bootstrap_vdb.sh` reference left untouched (separate known-broken item).
- `AGENTS.md` known-broken list — removed the `core/llm/llm-server/start-llm.sh` port-mismatch entry (line 176) because the subdir is now deleted. Reworded the `install.sh` entry (was about MODEL_URL/SHA256 placeholders, now about bootstrap_vdb.sh path).

## Notable findings

- `core/bot` consumer code is fully decoupled from the LLM backend — it only knows `LLM_ENDPOINT`. This made the swap low-risk and is the right design.
- The compose `volumes:` block still declares `openclaw_llm_model:` (deliberately, for back-compat with any external docs/scripts that may reference it). `openclaw-llm` no longer mounts it.
- `core/bot`'s `llm_client.py` has its own retry logic (`MAX_RETRIES=3`, `BACKOFF_BASE=0.5`). The proxy's `_call_gateway` has its own retry layer (`LLM_MAX_RETRIES=2`). Total worst-case retry budget is bounded but multiplicative; flagging for future tuning if latency becomes a concern.
- Cannot run live import tests of `core/llm/app.py` on the host: `requests` and `flask` are container-only deps per AGENTS.md. `py_compile` validates syntax. AST inspection confirms two routes registered: `POST /parse`, `GET /health`.

## Open threads

- User wires `AI_GATEWAY_BASE_URL`, `AI_GATEWAY_API_KEY`, `AI_GATEWAY_MODEL` in `.env` before first run. Service refuses to start otherwise.
- Not committed (per user pattern).
- `core/pca-backend/index.html` missing + import bugs (known-broken) — untouched.
- `bootstrap_vdb.sh` path bug (known-broken) — untouched.
- `core/vdb` tests not run; this change is in `core/llm` only and does not touch vdb.
