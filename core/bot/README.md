# BOT CONTAINER (`openclaw-bot` + `openclaw-worker`)

Thin Telegram frontend to the user-owned `~/ai-gateway`. Two processes share this image. All LLM work is delegated to the gateway. All git work for `/build` happens in the worker; chat for `/chat` is pure delegation.

```
Telegram → openclaw-bot → Redis → openclaw-worker → ~/ai-gateway → reply to Telegram
                                       │
                                       └── /build only: git clone → apply → commit → push → PR
```

Target: Raspberry Pi 5 (ARM64) & linux-rpi  
Memory Limit: 512MB per container  
Security Model: Zero Trust

---

## Purpose

`openclaw-bot` is the Telegram frontend. `openclaw-worker` is the queue consumer.

- **Bot**: Telegram polling, command parsing, RBAC, rate limit, job queuing. Never touches git or the gateway directly — only enqueues.
- **Worker**: Reads jobs from Redis. For each job, dispatches to either the build workflow (gateway → git → PR) or the chat workflow (gateway → text reply). Replies to Telegram.

The bot never:

- Accesses the host filesystem
- Executes shell commands on the host
- Exposes ports
- Runs as root

The worker additionally:

- Writes to `/sandbox` (the only writable path on its container — tmpfs-backed)
- Calls `~/ai-gateway` over HTTPS with a bearer token
- Uses `git` CLI + GitHub REST API (with `GITHUB_TOKEN`) for `/build` PRs

---

## Security

- Non-root user (`botuser`).
- `read_only: true` on root FS, `cap_drop: ALL`, `no-new-privileges: true`.
- `pids_limit: 100`, `mem_limit: 512MB`.
- `/sandbox` mounted as tmpfs — the only writable path on the worker.
- No docker.sock, no privileged flags, no host mounts.

Outbound HTTPS only to:

- Telegram API (`api.telegram.org`)
- `~/ai-gateway` (user-defined `AI_GATEWAY_BASE_URL`)
- GitHub REST API (`api.github.com`) — worker only, when opening PRs

Secrets (`TELEGRAM_TOKEN`, `AI_GATEWAY_API_KEY`, `GITHUB_TOKEN`) come from env only. Never written to disk, never logged.

**No API keys in any frontend** — this rule applies here too. The bot holds its own `TELEGRAM_TOKEN` (its identity, not a third-party credential) and the `AI_GATEWAY_API_KEY` / `GITHUB_TOKEN` it needs to do its work, but it never exposes any of these to Telegram, the dashboard, or any other surface.

---

## Commands

Owner-only (`ALLOWED_USER` enforced). Rate-limited at 10 commands/min.

| Command                          | What it does                                                                                                |
|----------------------------------|-------------------------------------------------------------------------------------------------------------|
| `/build [owner/repo] <feature>`  | Full coding workflow. Worker clones the repo, asks gateway for changes, applies, commits, pushes, opens PR. Reply: PR URL. If repo omitted, uses `DEFAULT_REPO`. |
| `/chat <text>`                   | Dictation. Free-text conversation with the gateway. Per-chat history (20 turns) maintained in Redis. Reply: gateway's response, chunked to fit Telegram. |
| `/jobs`                          | List recent jobs and their statuses.                                                                        |
| `/job <id>`                      | Status + result for a specific job.                                                                         |
| `/status`                        | System health: queue depth, processing count, dead-letter count.                                            |
| `/clear`                         | Wipe your chat history from Redis.                                                                          |
| `/model <name>`                  | Set per-chat model override for `/chat` jobs. Empty argument is rejected.                                   |

Anything else returns the help menu.

---

## Build workflow (`/build`)

1. **Parse**: bot extracts `repo` (optional) + `instruction` (required). Missing instruction → usage reply.
2. **Enqueue**: push `{id, chat_id, type: "build", repo, instruction, ts}` to Redis `queue:jobs`.
3. **Dequeue**: worker `brpoplpush` from `queue:jobs` → `queue:processing`.
4. **Status**: mark job `running` in Redis.
5. **Sandbox**: `github_client.clone_or_pull(repo, SANDBOX_DIR)`. Idempotent — pulls if exists.
6. **Branch**: `github_client.create_branch(SANDBOX_DIR, "dev-agent/<job-id-prefix>")`.
7. **Plan**: `ai_gateway_client.plan_changes(instruction, repo_context)` — returns `{files: [{path, action, content}]}`.
8. **Apply**: write/modify/delete files in the sandbox per the plan.
9. **Commit**: `github_client.commit_all(SANDBOX_DIR, message)`.
10. **Push**: `github_client.push(SANDBOX_DIR, branch_name)`.
11. **PR**: `github_client.open_pr(repo, branch_name, base, title, body)` via GitHub REST API.
12. **Reply**: send `Job <id> — PR opened: <url>` to Telegram.
13. **Cleanup**: mark job `complete`, lrem from `queue:processing`.

On any git/gateway failure: send error to Telegram, mark job `failed`. No retry — user re-runs `/build` if needed.

## Chat workflow (`/chat`)

1. **Parse**: bot extracts `instruction`. Missing → usage reply.
2. **Enqueue**: push `{id, chat_id, type: "chat", instruction, ts}` to Redis.
3. **Dequeue**: worker brpoplpush.
4. **History**: `ChatStore.history(chat_id)` → last 20 turns (list of `{role, content, ts}`).
5. **Chat**: `ai_gateway_client.chat(messages, system_prompt)` — `/v1/chat/completions` with the conversation, no `response_format`.
6. **Persist**: append user turn + assistant turn via `ChatStore.append`. List is trimmed to 20.
7. **Reply**: `_chunk_send(chat_id, response_text)` — splits on `\n\n` boundaries, ≤ `TELEGRAM_MAX_CHARS` per message.
8. **Cleanup**: mark job `complete`.

On failure: send `Chat failed: <err>` to Telegram, mark `failed`. No retry.

---

## Internal modules

| File                       | Purpose                                                                              |
|----------------------------|--------------------------------------------------------------------------------------|
| `bot.py`                   | Telegram polling, command dispatch, RBAC, rate limit, job queuing.                   |
| `queue_worker.py`          | Worker main loop; branches on `job_type` for build vs chat.                          |
| `ai_gateway_client.py`     | Three functions: `parse_instruction` (legacy planner), `chat` (free text), `plan_changes` (build JSON). Same bearer auth + retry layer. |
| `chat_store.py`            | Redis wrapper for `chat:{chat_id}:history` and `chat:{chat_id}:model`. Trim on append. |
| `telegram_sender.py`       | `_chunk_send(chat_id, text)` — chunked Telegram replies.                              |
| `github_client.py`         | `clone_or_pull`, `create_branch`, `commit_all`, `push`, `open_pr`. Git CLI + REST API. |
| `rate_limiter.py`          | Redis-backed sliding-window rate limiter (10/min).                                   |
| `config.py`                | Module-level env reads + defaults.                                                   |
| `Dockerfile`               | `python:3.11-slim`, non-root `botuser`, `git` CLI installed for the worker.          |

---

## Environment variables

Required:

- `TELEGRAM_TOKEN`
- `ALLOWED_USER` (Telegram user ID as int)
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`
- `AI_GATEWAY_BASE_URL`, `AI_GATEWAY_API_KEY`, `AI_GATEWAY_MODEL`
- `GITHUB_TOKEN` (scopes: `contents: write`, `pull-requests: write` on target repos)

Optional:

- `DEFAULT_REPO` — used when `/build` has no repo argument.
- `SANDBOX_DIR` — git workspace (default `/sandbox`).
- `CHAT_HISTORY_MAX_TURNS` — default 20.
- `TELEGRAM_MAX_CHARS` — default 3800.
- `LOG_LEVEL` — default `info`.

---

## Job state in Redis

| Key                       | Type | Purpose                                                  |
|---------------------------|------|----------------------------------------------------------|
| `queue:jobs`              | list | Pending jobs (LPUSH on enqueue, BRPOPLPUSH on dequeue).  |
| `queue:processing`        | list | In-flight (for crash recovery).                          |
| `queue:dead`              | list | Permanently failed (currently unused for `/build`/`/chat`). |
| `job:{id}`                | hash | Job status, result, retries, timestamps.                 |
| `jobs:index`              | zset | Job IDs ordered by creation time (for `/jobs`).          |
| `jobs:running`            | zset | Currently running job IDs.                               |
| `jobs:complete`           | zset | Completed job IDs.                                       |
| `chat:{chat_id}:history`  | list | Chat conversation turns, capped at `CHAT_HISTORY_MAX_TURNS`. |
| `chat:{chat_id}:model`    | str  | Per-chat model override (set via `/model`).              |
| `worker:heartbeat`        | str  | Worker liveness timestamp (TTL 30s).                     |

---

## Deployment

```bash
cp .env.example .env
# Fill in TELEGRAM_TOKEN, ALLOWED_USER, REDIS_PASSWORD, AI_GATEWAY_*, GITHUB_TOKEN
docker compose -f docker-compose.prod.yml up -d --build
```

## Verification

```bash
docker inspect openclaw-bot    # ReadOnlyRootFilesystem: true, no ports, no mounts except /sandbox
docker inspect openclaw-worker # same + GITHUB_TOKEN env present, /sandbox tmpfs mounted
docker logs openclaw-worker    # "Worker started (build+chat)..."
```

In Telegram:

```
/status             # queue depth = 0
/build myorg/myrepo add README section
/jobs               # see the job
/chat thanks!
```
