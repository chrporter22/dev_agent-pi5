# Review leave-off and plan next steps

- **Date:** 2026-10-31 00:08
- **Developer:** agent
- **Topic:** llm

## Request

User asked to "review leave off point and make a plan for next steps" (suffix: `LITELLM ESCALATE`). The leave-off point in question is `.ai/sessions/llm/2026-10-28-2053--LEAVE-OFF.md`, which says: planning complete, no code changes yet, awaiting explicit "proceed".

## What was done

This session — no code changes. The plan-first rule applied: load context, present review + plan, ask for explicit approval before any implementation.

### Context loaded

- `.ai/decisions/llm/2026-10-19--replace-local-qwen-with-litellm.md` — the LiteLLM gateway decision (the *why* behind the external gateway).
- `.ai/decisions/security/2026-10-28--no-api-keys-in-frontend-rls-in-database.md` — the security rules in force.
- `.ai/decisions/simplify/2026-10-24--strip-llm-and-vdb-keep-bot-pca.md` — the prior strip that removed `core/llm` + `core/vdb` and rewired `core/bot` directly to ai-gateway.
- `.ai/sessions/llm/2026-10-19-2052--swap-local-qwen-for-litellm.md` — original proxy-era work (now superseded by the simplify strip).
- `.ai/sessions/simplify/2026-10-24-1805--strip-llm-vdb-add-ai-gateway.md` + LEAVE-OFF — the simplify work that produced the current 6-service architecture.
- `.ai/sessions/llm/2026-10-28-2053--telegram-dictation-and-ai-gateway-review.md` + LEAVE-OFF — the revised-vision session that produced the 17-subtask / 5-phase plan awaiting "proceed".

### Current working-tree state (verified via `git status`)

On branch `main`, uncommitted:
- The 2026-10-24 simplify change (12 deletions from `core/llm/` and `core/vdb/`, 6 modifications including `docker-compose.prod.yml`, `.env.example`, `install.sh`, AGENTS.md, README.md, `core/bot/{bot,config,queue_worker}.py`).
- New `core/bot/ai_gateway_client.py` (the 2026-10-28 starting point — `parse_instruction()` only).
- New memory files in `.ai/decisions/{security,simplify}/` and `.ai/sessions/{llm,simplify}/`.
- Modified `core/bot/README.md` (PRD rewrite, 2026-10-28).
- Modified root `README.md` (PRD rewrite, 2026-10-28 — has the roadmap with the 5 phases).

## Where we left off

🟡 Planning complete. PRD + bot README rewritten. **No implementation code from the 17 subtasks yet.** User has not yet said "proceed".

The plan lives in `.ai/sessions/llm/2026-10-28-2053--LEAVE-OFF.md` lines 43–82 and is mirrored in root `README.md` lines 174–204.

### One-line status

Repo is being reoriented as a lightweight Telegram vertical to `~/ai-gateway` for AI coding work. Bot creates GitHub branches + PRs directly (gateway only does LLM inference). `core/ml` Keras + TFLite drop. pca-backend + node-api build fixes ship in the same change.

## Plan for next steps (the 5 phases)

Strict order. Verify at the end of each phase. No live Docker possible on host.

1. **Phase 1 — Chat / dictation core.** Extend `ai_gateway_client.py` with `chat()` (no `response_format`) + `plan_changes()` (structured JSON for `/build`). Add `chat_store.py` (Redis history, 20-turn cap). Add `telegram_sender.py` (`_chunk_send`). Extend `config.py`.
2. **Phase 2 — Git / PR workflow.** New `github_client.py` (git CLI + GitHub REST). Extend `bot.py` with `/build [owner/repo] <feature>`, `/chat <text>`, `/clear`, `/model <name>`. Rewrite `queue_worker.py` to branch on `job_type`.
3. **Phase 3 — Container wiring.** Dockerfile adds `git`. `docker-compose.prod.yml` adds `SANDBOX_DIR=/sandbox` tmpfs on worker only + `GITHUB_TOKEN` env. `.env.example` adds `GITHUB_TOKEN`, `DEFAULT_REPO`, `SANDBOX_DIR`.
4. **Phase 4 — ML cleanup + dashboard fixes.** Drop Keras + TFLite from `core/ml/`. Fix pca-backend build (`main.ts` → `main.tsx`, missing `index.html`, `globals.css` → `global.css`, nginx trailing slash). Fix node-api build (`redisHelpers.ts` → `redisHelper.ts`, `REDIS_URL` → `REDIS_HOST`+`REDIS_PORT`).
5. **Phase 5 — Decision record + verification + finalize.** Write `.ai/decisions/llm/2026-10-28--lightweight-vertical-to-ai-gateway.md` (the *why*). Update README roadmap. AST check + grep for stale symbols. Finalize session files. **No commit** (per repo pattern).

## Decision needed from user (this session)

Two questions to unblock Phase 1:

1. **Approval.** Do you approve the 5-phase / 17-subtask plan as written in the LEAVE-OFF file? If yes, start Phase 1?
2. **On `LITELLM ESCALATE`.** Per the LEAVE-OFF (lines 268–270), this is treated as a project-internal label confirming LiteLLM is the gateway tech — not an override of plan-first, not a new feature, not a separate mode. To escalate a chat to a bigger model, the planned `/model <name>` per-chat command is the intended path. **Confirm this interpretation**, or tell me you want `LITELLM ESCALATE` to mean something different (e.g., a separate system message added to the gateway call).

## Open threads

- User wires `.env` after implementation lands.
- Not committed (per repo pattern).
- `core/ml/embedding_client.py` removal + vdb-style data source are Phase 4 items.
- Live compose build / smoke-test cannot run on this host (no Docker daemon + no real env vars). Verification ceiling is `py_compile`, `npm run build`, AST, grep.

---

## Phase 1 — chat / dictation core (completed this session, 2026-10-31)

User approved the plan and the LITELLM ESCALATE clarification (chat-flow code path; security posture reaffirmed). All 4 subtasks done and verified.

### Subtasks landed

| # | File | Change |
|---|---|---|
| 1 | `core/bot/ai_gateway_client.py` | Added `chat(messages, system)` (free text, no `response_format`) and `plan_changes(instruction, repo_context)` (structured JSON with CI-workflow instruction in prompt). Refactored `_request_gateway` to return raw assistant content string + `_call_with_retry(body, parse_fn)` helper. `parse_instruction()` signature, body shape, and return type are byte-identical. Three system prompts: `PARSE_SYSTEM_PROMPT` (renamed from `SYSTEM_PROMPT`), `CHAT_SYSTEM_PROMPT`, `PLAN_CHANGES_SYSTEM_PROMPT`. |
| 2 | `core/bot/config.py` | Added `CHAT_HISTORY_MAX_TURNS=20`, `TELEGRAM_MAX_CHARS=3800`, `DEFAULT_REPO`, `SANDBOX_DIR="/sandbox"`. Renamed dead `SANDBOX_REPO` → `DEFAULT_REPO` (single-line, no callers). Left dead `REDIS_URL` alone (the live `REDIS_URL` issue is in `core/node-api`, Phase 4). |
| 3 | `core/bot/chat_store.py` (NEW) | `ChatStore` class backed by Redis. Keys: `chat:history:{chat_id}` (LIST, trimmed to `CHAT_HISTORY_MAX_TURNS` on every append) and `chat:model:{chat_id}` (STRING). Methods: `append`, `history`, `clear`, `get_model`, `set_model`. Uses `decode_responses=True`. |
| 4 | `core/bot/telegram_sender.py` (NEW) | `_chunk_send(chat_id, text)` (the public entry point per plan). Splits on `\n\n+` boundaries, greedy-chunks under `TELEGRAM_MAX_CHARS`. `_hard_split` fallback that prefers line breaks, hard-char-splits only when a single line exceeds the limit. Internal `_send` POSTs to Telegram. |

### Decisions taken this session (2026-10-31)

- **LITELLM ESCALATE = the `/chat` code path** (gateway → bot → user). Plus a security reaffirmation: no keys in frontend, RLS if SQLite added, Redis zero-trust with `ALLOWED_USER` gate as per-user RBAC. Recorded in `.ai/decisions/llm/2026-10-31--litellm-escalate-interpretation.md`.
- **Renamed dead `SANDBOX_REPO` → `DEFAULT_REPO`** in config.py to avoid two names for one concept. `REDIS_URL` left untouched (Phase 4 scope).
- **Internal refactor of `ai_gateway_client.py`**: extracted `_request_gateway` (raw content string) and `_call_with_retry(body, parse_fn)`. `parse_instruction` is back-compat identical (same body, same return dict shape, same retry behavior). Justified at 3 call sites per AGENTS.md rule on shared behavior extraction.

### Verification (host-side ceiling)

- `python3 -m py_compile core/bot/ai_gateway_client.py core/bot/config.py core/bot/chat_store.py core/bot/telegram_sender.py` → all OK.
- AST inspection of `ai_gateway_client.py`: `parse_instruction(instruction: str)`, `chat(messages: List[Dict[str, str]], system: str=CHAT_SYSTEM_PROMPT)`, `plan_changes(instruction: str, repo_context: Dict[str, Any])` — all present.
- AST inspection of `chat_store.py`: `ChatStore` class with `append`, `history`, `clear`, `get_model`, `set_model`.
- AST inspection of `telegram_sender.py`: `_chunk_send`, `_send`, `_hard_split` all present.
- Runtime imports of `ai_gateway_client` and `chat_store` cannot run on host (container-only deps: `requests`, `redis`). Same ceiling as the 2026-10-24 simplify work — py_compile + AST + grep is the verification ceiling.
- No secret-scan needed — these files read only `AI_GATEWAY_*` from env via `config.py`. No new env reads introduce new key material.

### Notable findings

- The bot's `core/bot/bot.py` and `core/bot/queue_worker.py` are **not yet wired** to `chat()`, `plan_changes()`, `ChatStore`, or `_chunk_send` — that's Phase 2 (subtasks 6, 7). The new code is intentionally inert until Phase 2 lands.
- `SANDBOX_REPO` was dead. Removing it now removes the trap of having two names for one concept before Phase 2 wires `DEFAULT_REPO` into `queue_worker.py` for the `/build` flow.
- `_chunk_send` is exposed as the public entry point despite the leading underscore, per the plan. The underscore distinguishes it from a future non-chunked `send_message` helper that may be added later.

### Working tree state after Phase 1 (uncommitted)

```
 M core/bot/config.py             # +CHAT_HISTORY_MAX_TURNS, +TELEGRAM_MAX_CHARS, +DEFAULT_REPO, +SANDBOX_DIR; renamed SANDBOX_REPO → DEFAULT_REPO
 M core/bot/ai_gateway_client.py  # parse_instruction + chat + plan_changes; shared retry helper
?? core/bot/chat_store.py         # NEW
?? core/bot/telegram_sender.py    # NEW
```

(plus the uncommitted 2026-10-24 simplify work, root README + bot README PRD rewrites from 2026-10-28, and the rest of the LEAVE-OFF plan still pending).

### Open threads (after Phase 1)

- Phase 2 (next): `core/bot/github_client.py` (NEW), wire `/build [owner/repo] <feat>`, `/chat`, `/clear`, `/model` into `bot.py`, rewrite `queue_worker.py` to branch on `job_type`.
- Phase 3: container wiring (Dockerfile adds `git`, compose adds `SANDBOX_DIR` tmpfs, `.env.example` adds `GITHUB_TOKEN` / `DEFAULT_REPO` / `SANDBOX_DIR`).
- Phase 4: ML cleanup + pca-backend / node-api build fixes.
- Phase 5: decision record, README roadmap flip, grep/AST check, finalize.

### To resume

- Phase 1 complete and verified. Awaiting explicit "proceed" before starting Phase 2.

---

## Phase 2 — git / PR workflow (completed this session, 2026-10-31)

User approved an expanded goal mid-session: bot is a plugin/vertical for `~/ai-gateway`; redis gets full per-service ACLs (RLS-equivalent); `.github/actions/` + workflows ship in this repo; `/pr` Telegram commands re-added (list/approve/show); ai-gateway stays external with healthcheck.

Three open questions were asked and the user picked all three recommended options:
- Redis ACL scope: **Full per-service users + key-pattern ACLs**.
- PR review/approve UX: **Re-add `/pr` Telegram commands** (list/approve/<url|num>).
- ai-gateway in compose: **External**; bot waits via healthcheck.

### Subtasks landed

| # | File | Change |
|---|---|---|
| 5 | `core/bot/github_client.py` (NEW) | Git CLI wrapper (`clone_or_pull`, `create_branch`, `commit_all`, `push`) + GitHub REST (`open_pr`, `list_prs`, `get_pr`, `merge_pr`). `_rest_call` retries 5xx + 429. `commit_all` returns `bool` so worker can skip push when nothing changed. URL-or-number identifier parsing for PRs. `merge_pr` handles 405 (branch protection / missing merge scope) gracefully. |
| 6 | `core/bot/bot.py` | New commands: `/build [owner/repo] <feat>` (extended), `/chat <text>`, `/clear`, `/model <name>`, `/pr list`, `/pr <url\|num>`, `/pr approve <url\|num>`. New `queue_chat()`. `list_jobs` and `get_job_status` show `type`, `repo`, `description`, `pr_url`. `get_system_status` shows worker heartbeat. Uses `_chunk_send` for long PR list / detail output. Help text rewritten. |
| 7 | `core/bot/queue_worker.py` | Full rewrite. Branches on `job["type"]`. `process_build_job`: clone → branch → `plan_changes` → `_apply_changes` (path-traversal guarded) → commit → push → `open_pr`. `process_chat_job`: load history via `ChatStore` → resolve model override → `chat(messages, model=...)` → append turns → `_chunk_send` reply. Retry + dead-letter preserved. |
| 7b | `core/bot/ai_gateway_client.py` | Tweak: `chat(messages, system, model=None)` accepts optional per-chat model override; falls back to `AI_GATEWAY_MODEL` env. |

### Decisions taken this session (2026-10-31, additions)

- **PR branch naming**: `dev-agent/{job_id[:8]}`. Always off `main`. Bot never writes to `main` (consistent with prior project rule).
- **Apply changes path-traversal guard**: `_apply_changes` rejects any path that, after `os.path.normpath`, starts with `..` or is absolute, AND verifies the resolved absolute path is under the sandbox dir. Two-layer check.
- **Empty-plan handling**: If `plan_changes` returns `{files: []}` or no files, the worker marks the job complete with a clear message instead of failing the job.
- **No-changes-to-commit handling**: `commit_all` returns `False` if `git status --porcelain` is empty; worker marks complete with a clear message and skips `push`.
- **PR merge handling**: `merge_pr` returns a dict with `merged: False` and a human-readable message on 405 (branch protection), instead of raising. This lets the bot reply with a useful error instead of dead-lettering the job.
- **Chat job type**: `queue_chat` writes `type: "chat"` to the job hash; worker reads `job.get("type", "build")` for back-compat with old build-only jobs in Redis (in case any pre-existing jobs are still queued).
- **Worker tmpfs sandbox**: `/sandbox` is the canonical path inside the worker container (Phase 3 will add the tmpfs mount to `docker-compose.prod.yml`; for now the worker falls back to cwd if the path doesn't exist).

### Verification (host-side ceiling)

- `python3 -m py_compile` on all 8 `core/bot/*.py` files → all OK.
- AST inspection of public surface:
  - `ai_gateway_client.py`: `parse_instruction`, `chat(messages, system, model=None)`, `plan_changes`.
  - `chat_store.py`: class `ChatStore` with `__init__`, `append`, `history`, `clear`, `get_model`, `set_model`.
  - `telegram_sender.py`: `_chunk_send`, `_send`, `_hard_split`.
  - `github_client.py`: `clone_or_pull`, `create_branch`, `commit_all` (returns `bool`), `push`, `open_pr`, `list_prs`, `get_pr`, `merge_pr`.
  - `bot.py`: `handle_message`, `handle_pr_command`, `queue_build`, `queue_chat`, `list_jobs`, `get_job_status`, `get_system_status`, `poll`.
  - `queue_worker.py`: `process_job`, `process_build_job`, `process_chat_job`, `_gather_repo_context`, `_apply_changes`, `_format_pr_body`, `_detect_language`.
- Path-traversal guard in `_apply_changes` confirmed via AST text scan.
- Runtime tests require `redis`, `requests` (container-only deps); not runnable on host.
- **Cannot run live yet**: worker needs `git` CLI (Phase 3 Dockerfile), `/sandbox` tmpfs mount (Phase 3 compose), `GITHUB_TOKEN` env (Phase 3 .env.example).

### Working tree state after Phase 2 (uncommitted)

```
 M core/bot/bot.py                # +/chat /clear /model /pr /build[repo]; queue_chat; updated status
 M core/bot/config.py             # (from Phase 1: 4 new env reads; renamed SANDBOX_REPO → DEFAULT_REPO)
 M core/bot/queue_worker.py       # rewrite: branches on job_type; build+chat flows
 M core/bot/ai_gateway_client.py  # chat() gets optional model arg
?? core/bot/chat_store.py         # NEW (Phase 1)
?? core/bot/telegram_sender.py    # NEW (Phase 1)
?? core/bot/github_client.py      # NEW (Phase 2)
```

### Open threads (after Phase 2)

- **Phase 3** (next): container wiring — Dockerfile adds `git` CLI, compose adds `/sandbox` tmpfs + `GITHUB_TOKEN` + per-service Redis users (the full ACL migration decided this session), `.env.example` adds the new vars.
- **Phase 4**: ML cleanup + pca-backend + node-api build fixes.
- **Phase 5**: ship `.github/workflows/{ci,deploy,build-pr}.yml` + `.github/actions/docker-build/action.yml`. Write decision files (`lightweight-vertical-to-ai-gateway.md` and `redis-rls-acls.md`). Update README roadmap. AST/grep verification.
- **Cannot reach `LITELLM EXECUTE`**: `core/llm/` was deleted in 2026-10-24 simplify. Confirmed dead. Not reintroducing.

### To resume

- Phase 1 + Phase 2 complete and verified. Awaiting explicit "proceed" before starting Phase 3 (container wiring + Redis ACLs).

---

## Phase 3 — container wiring + Redis ACLs (completed this session, 2026-10-31)

User approved Phase 3: full Dockerfile + compose + .env.example additions. The big addition is per-service Redis ACLs (Redis 7 user+key-pattern permissions), which is the security work the user explicitly asked for ("add rls to redis kvs"). The worker also gets `git`, a `/sandbox` tmpfs, and a gateway-reachability healthcheck.

### Subtasks landed

| # | File | Change |
|---|---|---|
| 3.1 | `core/bot/config.py` | Added `GITHUB_TOKEN`, `REDIS_USER` (default `"bot"`). Removed dead `REDIS_URL`. |
| 3.2 | `core/bot/bot.py`, `queue_worker.py`, `chat_store.py` | All Redis clients now pass `username=REDIS_USER`. |
| 3.3 | `core/bot/Dockerfile` | Added `RUN apk add --no-cache git` after the base image. Non-root `botuser` preserved. |
| 3.4 | `core/bot/healthcheck.py` (NEW) | TCP-reachability check on `AI_GATEWAY_BASE_URL` (parses URL, `socket.create_connection((host, port), timeout=5)`). Exits non-zero on failure. |
| 3.5 | `core/ml/config.py` | Added `REDIS_USER` (default `"ml"`). |
| 3.6 | `core/ml/redis_store.py` | Redis client passes `username=REDIS_USER`. |
| 3.7 | `core/node-api/src/redis/client.ts` | Switched from `REDIS_URL` to explicit `host`/`port`/`username`/`password` fields. Removed the known-broken `REDIS_URL` fallback. |
| 3.7b | `core/node-api/src/routes/ml.ts` | Pulled forward from Phase 4 for verifiability: fixed `redisHelpers` → `redisHelper` import (file on disk is `redisHelper.ts`); changed Python-style `# ---` comment to TS `// ---` on line 141. |
| 3.8 | `redis/redis.conf` (NEW) | bind `0.0.0.0`, `appendonly no`, `save ""`, `aclfile /usr/local/etc/redis/users.acl`. Renames `FLUSHDB/FLUSHALL/KEYS/CONFIG/SHUTDOWN/DEBUG` to empty (protocol-level denial). |
| 3.8 | `redis/users.acl.template` (NEW) | 5 users: `default off`; `bot` (chat/queue/job/rate/worker keys, full commands minus dangerous); `worker` (chat/queue/job/worker keys, same); `ml` (pca/drift/risk/model/ml keys, same); `nodeapi` (pca/drift/risk + `ml:heartbeat`/`ml:last_run`, READ-ONLY via `+get +hget +hgetall +lrange +zrange +zrevrange +exists +type +ttl +scan -@all`). Passwords are `${REDIS_PASSWORD_*}` placeholders. |
| 3.8 | `redis/entrypoint.sh` (NEW) | `sed` substitutes `${REDIS_PASSWORD_*}` placeholders from the container env, `chmod 644`s the substituted ACL, `exec redis-server /usr/local/etc/redis/redis.conf`. Bash syntax checked. |
| 3.9 | `docker-compose.prod.yml` | Full rewrite. Per-service `REDIS_USER` + `REDIS_PASSWORD_${SERVICE}` envs; `redis` service uses `entrypoint: /usr/local/etc/redis/entrypoint.sh` + mounts `redis.conf`, `users.acl.template`, `entrypoint.sh` read-only + tmpfs on `/usr/local/etc/redis` for the substituted ACL; worker gets `GITHUB_TOKEN`, `DEFAULT_REPO`, `SANDBOX_DIR=/sandbox`, tmpfs on `/sandbox`, and `healthcheck: python /app/healthcheck.py`; redis healthcheck uses `redis-cli --user nodeapi --pass "$$REDIS_PASSWORD_NODEAPI" ping`. `pca-backend` unchanged (no Redis access). |
| 3.10 | `.env.example` | Reorganized: per-service `REDIS_USER_*` + `REDIS_PASSWORD_*` placeholders; `GITHUB_TOKEN`, `DEFAULT_REPO`, `SANDBOX_DIR=/sandbox`; legacy `REDIS_PASSWORD` kept for back-compat. |

### Decisions taken this session (Phase 3 additions)

- **Per-service ACL plan** (`redis/users.acl.template`): `bot` ↔ `worker` ↔ `ml` ↔ `nodeapi`. `default` is `off`. `nodeapi` is read-only by command set (`+get +hget +hgetall +lrange +zrange +zrevrange +exists +type +ttl +scan -@all`), not just key patterns — defense in depth.
- **Password substitution via `sed`**: chose `sed` over `envsubst` because `redis:7-alpine` does not include `gettext`. Chose `#` as delimiter (not `|` or `/`) to be safe with typical alphanumeric/base64 passwords.
- **Substituted ACL file permissions**: `chmod 644` on the in-container file (mounted under tmpfs). The bind-mounted source template stays `ro`. The substituted file is only readable inside the redis container — same blast radius as before.
- **Redis container volumes**: `redis.conf` + `users.acl.template` + `entrypoint.sh` are bind-mounted `ro`; `/usr/local/etc/redis` is a tmpfs so the substituted ACL file does not persist across restarts (intentional).
- **Worker healthcheck**: TCP-only (not HTTP), since the gateway endpoint shape isn't fixed and we only want liveness, not full response validation. Returns non-zero on connection refused / DNS failure.
- **`core/node-api/src/routes/ml.ts` Phase 4 fixes pulled forward**: 2 trivial fixes (1 import name + 1 char) needed for `npm run build` to pass. Logged here so the Phase 4 worklist is updated.

### Verification (host-side ceiling)

- `python3 -m py_compile core/bot/*.py core/ml/config.py core/ml/redis_store.py` → all OK.
- `cd core/node-api && npm run build` → OK (after pulling the 2-line routes/ml.ts fix forward).
- `python3 -c "import yaml; yaml.safe_load(open('docker-compose.prod.yml'))"` → OK.
- `bash -n redis/entrypoint.sh` → OK.
- sed substitution smoke test → produces a valid ACL with passwords filled in.
- `python3 core/bot/healthcheck.py` with empty env → exits 1 ("AI_GATEWAY_BASE_URL not set"); with `http://127.0.0.1:1` → exits 1 ("Connection refused").
- Compose structural invariants (asserted via Python YAML parse):
  - `openclaw-worker` has `SANDBOX_DIR=/sandbox`, `GITHUB_TOKEN`, `/sandbox` tmpfs, `healthcheck`.
  - `redis` has `entrypoint: /usr/local/etc/redis/entrypoint.sh`, all three volumes mounted, all four `REDIS_PASSWORD_*` envs in scope.
  - `openclaw-bot` / `openclaw-worker` / `openclaw-ml` / `node-api` each have their own `REDIS_USER=` + `REDIS_PASSWORD_*`.
- Secret-scan: `grep -rE 'sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{20,}'` across `core/`, `redis/`, `docker-compose.prod.yml`, `.env.example` → zero hits.
- Live Docker build/run cannot happen on this host (no Docker daemon, no real env vars).

### Working tree state after Phase 3 (uncommitted)

```
 M .env.example
 M core/bot/Dockerfile
 M core/bot/bot.py
 M core/bot/config.py
 M core/bot/queue_worker.py
 M core/ml/config.py
 M core/ml/redis_store.py
 M core/node-api/src/redis/client.ts
 M core/node-api/src/routes/ml.ts          # Phase 4 fixes pulled forward
 M docker-compose.prod.yml
?? core/bot/ai_gateway_client.py            # Phase 1
?? core/bot/chat_store.py                   # Phase 1
?? core/bot/github_client.py                # Phase 2
?? core/bot/healthcheck.py                  # Phase 3
?? core/bot/telegram_sender.py              # Phase 1
?? redis/redis.conf                         # Phase 3
?? redis/users.acl.template                 # Phase 3
?? redis/entrypoint.sh                      # Phase 3
```

(plus the pre-existing 2026-10-24 simplify changes, the 2026-10-28 PRD rewrites, and the rest of the 5-phase plan still pending: Phase 4 ML cleanup + pca-backend fixes, Phase 5 decision files + .github/ workflows + AGENTS.md updates + final verification.)

### Open threads (after Phase 3)

- **Phase 4** (next): `core/ml/` Keras + TFLite drop + `embedding_client.py` removal; pca-backend build fixes (`main.ts` → `main.tsx`, missing `index.html`, `globals.css` → `global.css`, nginx trailing slash). `core/node-api` build fixes already done in Phase 3 (pulled forward).
- **Phase 5**: ship `.github/workflows/{ci,deploy,build-pr}.yml` + `.github/actions/docker-build/action.yml`. Write decision files (`lightweight-vertical-to-ai-gateway.md`, `redis-rls-acls.md`). Update README roadmap. AST/grep final verification.
- **Live verification (cannot run on host)**: needs Docker daemon + real env vars. User wires `.env` then `docker compose -f docker-compose.prod.yml up -d --build` to confirm.

### To resume

- Phase 1 + 2 + 3 complete and verified. Awaiting explicit "proceed" before starting Phase 4.

---

## Skills audit + Phase 4 ML cleanup + pca-backend fixes (this session, 2026-10-31)

Mid-Phase 4, the user pivoted to "review `~/agent-skills` and any missing skills add to this repo" with `LITELLM ESCALATE` suffix. `LITELLM ESCALATE` is the project-internal label meaning "the gateway tech is LiteLLM" — no override of plan-first, no new feature. Plan-first applied: presented the audit + plan, got user approval via a four-question form, then executed.

### Subtasks landed

| # | File | Change |
|---|---|---|
| S1 | `.claude/skills/docker-testing/SKILL.md` (NEW) | Copied from `~/agent-rules/repo-template` and adapted: agent-host has no Docker daemon, so added a "no daemon" fallback ladder (container → host toolchain project-scoped only → report the gap). Noted that `.gitignore` does not list `node_modules/` or `package-lock.json`. |
| S2 | `.claude/skills/security-rbac-zero-trust/SKILL.md` (NEW) | Copied and adapted: rule 4 was Postgres RLS, swapped for **per-service Redis ACLs** (Phase 3 work). RBAC section pruned to the single-operator `ALLOWED_USER` model this repo actually has. Path-containment on worker writes added as zero-trust note. |
| S3 | `.claude/skills/eda-econometrics-numpy/SKILL.md` (NEW) | Trimmed from 301 to 131 lines. Dropped classical assumption tests (RESET, Durbin-Watson, Breusch-Pagan, White, VIF, Jarque-Bera, Hausman IV) and the numpy regression implementations — this repo has no training data and no supervised model after Phase 4. Kept and rewrote: numpy-only principle, PCA-from-numpy (SVD preferred; eigh-on-covariance is fine), feature-selection order, eval contract adapted to no-train/val/test, senior gotchas rewritten for post-Keras risks. |
| S4 | `.claude/skills/no-agent-push/SKILL.md` (NEW) | Copied as-is with one `### In this repo` clarification: the bot pushes and opens PRs by design; the skill governs the agent, not the bot. |
| S5 | `.claude/skills/pii-redaction/SKILL.md` (NEW) | Copied as-is. Identical across all sibling repos. |
| S6 | `.claude/skills/repo-index/SKILL.md` (NEW) | Copied as-is with `## In this repo` note: index not built yet; building is a separate opt-in step. |
| S7 | `.claude/skills/data-science/SKILL.md` (REWRITE) | Was TensorFlow/Keras/FastAPI/`contract/` workflow; none apply. Rewritten to numpy PCA + drift + rules-based risk + Redis serving path. 79 lines, repo-specific. |
| 14 | `core/ml/risk_classifier.py` (NEW) | `classify_risk(drift_score) -> (label, confidence)`. BANDS table from `config.DRIFT_THRESHOLD_*`. Confidence is normalized distance to the band edge mapped to `[0.5, 1.0]` — deterministic rule margin, not a learned probability. |
| 15 | `core/ml/ml_worker.py` (REWRITE) | Drops Keras training, TFLite inference, and the vdb-based `fetch_embeddings()`. Loop runs PCA → drift → rules-based risk → Redis when data is present; writes heartbeat and skips when not (dormant by design until a source is wired). Always writes `ml:heartbeat` + `ml:last_run` so the dashboard's WorkerCard stays accurate. |
| 16 | `core/ml/model_trainer.py`, `core/ml/model_runtime.py`, `core/ml/embedding_client.py` | DELETED. Keras, TFLite runtime, and the vdb-backed embedding client are gone. |
| 17 | `core/ml/requirements.txt` | `tensorflow`, `tflite-runtime`, `scikit-learn`, `joblib`, `scipy` removed. Final deps: `numpy`, `redis`, `requests`. |
| 18 | `core/ml/Dockerfile` | `mkdir -p /app/models` removed (no models anymore). `/app/data` mkdir retained. |
| 19 | `core/ml/README.md` (REWRITE) | Full PRD rewrite to v2.0: rules-based risk in Step 4, no model, Redis ACL ownership of `ml` key patterns, dormant-when-no-source semantics. |
| 20 | `core/pca-backend/src/main.ts` → `src/main.tsx` (NEW file + delete old) | Renamed to `.tsx` (JSX content). Fixed css import: `./styles/globals.css` → `./styles/global.css` (the file on disk was always `global.css`). |
| 21 | `core/pca-backend/index.html` (NEW) | Vite entry; references `/src/main.tsx`. Was missing — Vite build was failing silently. |
| 22 | `core/pca-backend/src/App.tsx` | Fixed line-broken `import Dashboard\nfrom "./pages/Dashboard"` to single line. |
| 23 | `core/pca-backend/nginx.conf` | Removed trailing slash on `proxy_pass http://node-api:3000;` (the slash was stripping `/api/` prefix and breaking all dashboard-to-API calls). |
| 24 | `core/pca-backend/src/types/ml.ts` | Made `risk?: string` and `confidence?: number` optional (decision #14: dashboard must still render after ML drop; confidence can be absent when Redis is fresh). |
| 25 | `core/pca-backend/src/components/cards/RiskCard.tsx` | Handles undefined `risk` (renders "Unknown") and undefined `confidence` (renders "—"). |
| 26 | `AGENTS.md` | Service description for `core/ml` no longer mentions Keras/TFLite. "Known-broken, pre-existing" list pruned: 3 items moved to a "Fixed by Phase 3 + Phase 4" sub-list (pca-backend build, `redisHelpers` import, `REDIS_URL`, `embedding_client.py`, nginx trailing slash). |
| 27 | `core/pca-backend/README.md`, `core/node-api/README.md` | Stale references to `globals.css`, `redisHelpers.ts`, and `REDIS_URL` updated to the post-Phase-3/4 reality. |
| 28 | `.ai/decisions/skills/2026-10-31--adopt-company-skills-set-adapt-for-repo.md` (NEW) | Decision record for the skills audit and adoption. |

### Decisions taken this session (Phase 4 + skills, 2026-10-31)

- **Source-of-truth for skills: `~/agent-rules/repo-template`.** That is the company canonical. `~/agent-skills` does not exist. Other sibling directories (`agent-rules-qwen2.5-coder`, `ai-gateway`, `opencode-pi`, `webhook-switchboard`) are subsets or variants.
- **Skills copy strategy: adapt where it conflicts.** Picked from four options. Verbatim would contradict this repo (Postgres RLS, no Docker fallback); rewrite-everything would lose the company standard; the middle path matches what was actually needed.
- **`data-science` skill rewritten, not deleted.** The old skill directed agents to a stack that AGENTS.md forbids and Phase 4 invalidates. Replacing it in place keeps existing references working.
- **`eda-econometrics-numpy` trimmed, not full copy.** The full 301-line copy is Kennedy econometrics — relevant for supervised regression, which this repo no longer has. The numpy-only + PCA + drift half is what we keep.
- **Keras + TFLite gone.** Confirmed dead after Phase 4. `requirements.txt` shrinks to `numpy`, `redis`, `requests`. `/app/models` directory removed from `core/ml/Dockerfile`. `risk_classifier.py` is the deterministic replacement.
- **`ml:heartbeat` always written.** Even when the data source is empty, the worker writes the heartbeat so the dashboard's WorkerCard stays accurate. This is a deliberate UX choice — "Offline" should mean "the worker is broken", not "the source is empty".
- **`risk_classifier` confidence is a rule margin, not a learned probability.** It is the normalized distance from the band edge, mapped to `[0.5, 1.0]`. The dashboard multiplies it by 100 and renders a percentage; the README and skill make clear it is a rule-side metric.
- **`risk:latest` and `model:prediction` both written.** Back-compat — the Node API reads `model:prediction`, older or third-party readers might read `risk:latest`. Same value in both.
- **`confidence` and `risk` are optional on `PcaSummary`.** Honors decision #14 from the LEAVE-OFF (dashboard must render after ML drop). Handles the case where Redis is fresh and ML has not yet run.
- **Skill scope clarification on `no-agent-push`.** This repo's *bot* pushes to GitHub by design. The skill governs the **agent**, not the bot. Without the note, a future reader would see the skill and the bot and conclude they contradict.
- **Skipped: `code-navigation`, `context-compiler` (qwen-3B tuned), `kennedy-assumption-tests` (empty dir in ai-gateway).** Noted in the decision record so future sessions don't repeat the survey.

### Verification (host-side ceiling)

- `python3 -m py_compile core/ml/*.py core/bot/*.py core/bot/healthcheck.py` → all OK.
- AST on the new `core/ml/ml_worker.py`: `run_cycle`, `main`, `_classify_drift`, `_heartbeat`, `_load_embeddings` present.
- AST on `core/ml/risk_classifier.py`: `classify_risk`, `_band_margin` present.
- `npm install` + `npm run build` in `core/pca-backend/` → OK. Output: `dist/index.html`, `dist/assets/index-*.css`, `dist/assets/index-*.js`. Vite-injected `<script type="module" crossorigin src="/assets/index-...">` into `dist/index.html`.
- `npm run build` in `core/node-api/` → OK (no change since Phase 3, but re-run to confirm).
- `python3 -c "import yaml; yaml.safe_load(open('docker-compose.prod.yml'))"` → OK (no change).
- `bash -n redis/entrypoint.sh` → OK (no change).
- `grep -rnE 'Keras|TFLite|tflite|model\.keras|embedding_client|globals\.css|redisHelpers' --include='*.{py,ts,tsx,js,css,html,yml,yaml,conf,json,md}' core/ redis/ AGENTS.md README.md` → only historical references remain (`risk_classifier.py` comment, `AGENTS.md` "Fixed by Phase 3 + Phase 4" line, README docs fixed in this PR). No live code references.
- `grep -rnE 'tensorflow|tflite-runtime|joblib|scikit-learn|^scipy$' core/` → zero hits.
- `grep -rnE 'REDIS_URL' core/ redis/ docker-compose.prod.yml .env.example` → only in fixed `core/node-api/README.md` (now describes the per-field config). No live code references.
- `grep -rE 'sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{20,}' core/ redis/ docker-compose.prod.yml .env.example` → zero hits (secret scan).
- Live Docker build/run cannot happen on host (no Docker daemon, no real `.env`).

### Working tree state (uncommitted)

```
 M .claude/skills/data-science/SKILL.md           # rewritten to numpy/rules-only
?? .claude/skills/docker-testing/                 # NEW (adapted)
?? .claude/skills/eda-econometrics-numpy/         # NEW (trimmed)
?? .claude/skills/no-agent-push/                  # NEW (with in-repo note)
?? .claude/skills/pii-redaction/                  # NEW (verbatim)
?? .claude/skills/repo-index/                     # NEW (with in-repo note)
?? .claude/skills/security-rbac-zero-trust/       # NEW (Redis ACL adaptation)
 M AGENTS.md                                      # core/ml service description; broken-list pruning
 M core/ml/config.py                              # env reads + threshold constants (Phase 4)
 M core/ml/Dockerfile                             # removed /app/models mkdir
 M core/ml/ml_worker.py                           # numpy + rules; no model; always heartbeat
 M core/ml/README.md                              # v2.0 PRD rewrite
 M core/ml/redis_store.py                         # REDIS_USER (Phase 3)
 M core/ml/requirements.txt                       # tensorflow/tflite-runtime/sklearn/joblib/scipy removed
 D core/ml/embedding_client.py
 D core/ml/model_runtime.py
 D core/ml/model_trainer.py
?? core/ml/risk_classifier.py                     # NEW (Phase 4)
 M core/node-api/README.md                        # redisHelpers -> redisHelper, REDIS_URL -> fields
 M core/pca-backend/README.md                     # globals.css -> global.css
 M core/pca-backend/nginx.conf                    # trailing slash removed
 M core/pca-backend/src/App.tsx                   # import fixed
 D core/pca-backend/src/main.ts
 M core/pca-backend/src/components/cards/RiskCard.tsx   # optional risk/confidence
 M core/pca-backend/src/types/ml.ts               # risk/confidence optional
?? core/pca-backend/index.html                    # NEW (Vite entry)
?? core/pca-backend/src/main.tsx                  # NEW (renamed + css fix)
?? .ai/decisions/skills/2026-10-31--adopt-company-skills-set-adapt-for-repo.md
```

(Plus the uncommitted Phase 1+2+3 work and the pre-existing 2026-10-24 simplify deletions of `core/llm/`, `core/vdb/`, `core/bot/llm_client.py`, `bootstrap_vdb.sh`.)

### Known minor pre-existing issues (not addressed here, noted for future sessions)

- `.gitignore` does **not** list `node_modules/` or `package-lock.json`. A host-side `npm install` will create both as untracked. The new `docker-testing` skill mentions this. Not fixed in this change — separate cleanup task.
- `kennedy-assumption-tests` is an empty directory under `~/ai-gateway/.claude/skills/`. Not this repo's problem; flag in the `ai-gateway` repo's own audit.
- `.ai/index/` is not built. The `repo-index` skill is installed but the index is not generated. Opt-in for a future session.

### To resume

- Phase 1 + 2 + 3 + 4 complete and verified. Skills set adopted.
- Phase 5 (from the LEAVE-OFF plan) remaining: ship `.github/workflows/{ci,deploy,build-pr}.yml` + `.github/actions/docker-build/action.yml`. Write `.ai/decisions/llm/2026-10-28--lightweight-vertical-to-ai-gateway.md` (the *why*). Update root `README.md` roadmap to flip Phase 4 to done. AST/grep final verification. **No commit** (per repo pattern).

