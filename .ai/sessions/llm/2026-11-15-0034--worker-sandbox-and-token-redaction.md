# Session: Worker /sandbox permission + GITHUB_TOKEN redaction in error messages

**Date**: 2026-11-15
**Task**: Investigate why `job:8471cbb9-3368-40cd-96b2-74be6234a209`
failed permanently and ended up in the dead-letter queue, fix it,
verify both fixes against a real worker run.

## Diagnosis

`docker logs openclaw-worker` showed three identical attempts, then
`Job failed permanently`:

```
RuntimeError: git clone … /sandbox failed: /sandbox/.git: Permission denied
```

Inside the container:

```
drwxr-xr-x  2 root   root   40 /sandbox
uid=100(botuser) gid=101(botgroup) CapEff: 0000000000000000
```

Two security choices collide:

1. `core/bot/Dockerfile:15-17` chowns `/app` to `botuser:botgroup` and
   drops to that user with `USER botuser`. `cap_drop: ALL`,
   `no-new-privileges`. Good.
2. `docker-compose.prod.yml:131-133` mounts `/sandbox` as tmpfs with
   **no `uid`/`gid`/`mode` set** → Docker defaults to `root:root`,
   `mode=0755`.

Result: `botuser` falls into "others" → only `r-x` → can read
`/sandbox` but cannot create `/sandbox/.git`. Every `/build` job has
been failing this way since the worker was rebuilt with `USER botuser`.
`/chat` jobs don't touch `/sandbox`, so they appeared to work and
masked the bug.

## What was done

### Subtask 1 — Fix /sandbox tmpfs ownership

`docker-compose.prod.yml:131-133` — `tmpfs:` for `/sandbox` now sets
the mount options:

```yaml
    tmpfs:
      - /tmp
      - /sandbox:size=100m,uid=100,gid=101,mode=755
```

Docker compose accepts `size`, `uid`, `gid`, `mode` on tmpfs mounts.
The tmpfs is now owned by `botuser:botgroup` from first mount, no
Dockerfile or entrypoint change needed.

### Subtask 2 — Redact GITHUB_TOKEN from git error messages

`core/bot/github_client.py:23-37` — `clone_or_pull` builds the clone
URL with the token inline (`f"https://x-access-token:{GITHUB_TOKEN}@…"`).
On any failure, `_run_git` echoed `result.stderr` (which contains the
URL) and `' '.join(args)` (which contains the URL) straight into a
`RuntimeError`. That message landed in:

- `docker logs openclaw-worker` (visible to anyone with docker access)
- the `error` field of `job:<id>` in Redis (HGETALL confirmed)
- the `queue:dead` payload

`_run_git` now scrubs both `args` and `stderr` for `GITHUB_TOKEN`
before raising, replacing it with `<REDACTED:TOKEN>`:

```python
redacted = [
    a.replace(GITHUB_TOKEN, "<REDACTED:TOKEN>") if GITHUB_TOKEN else a
    for a in args
]
stderr = (
    result.stderr.replace(GITHUB_TOKEN, "<REDACTED:TOKEN>")
    if GITHUB_TOKEN else result.stderr
)
raise RuntimeError(
    f"git {' '.join(redacted)} failed: {stderr.strip()}"
)
```

The token is still in `.env` (gitignored) and is still passed to git
inline (the only auth method the CLI uses for clone). The change is
purely about error-message exposure.

### Subtask 3 — Rebuild worker, re-queue dead job, verify

| Check | Result |
|-------|--------|
| `docker compose up -d --build openclaw-worker` | rebuilt clean, container Started |
| `ls -la /sandbox` inside worker | `drwxr-xr-x botuser botgroup` (was `root:root`) |
| `mount \| grep sandbox` | `tmpfs … uid=100,gid=101,mode=755` |
| `git init /sandbox/testdir` inside worker | succeeded, `.git` created |
| Synthetic clone of a bogus repo with token inline | error contains `<REDACTED:TOKEN>`, zero `github_pat_` substring in stderr |
| Re-queue dead job `8471cbb9…` from `queue:dead` → `queue:jobs` | accepted, worker picked it up |
| `docker logs openclaw-worker` after re-run | error now reads `Repository not found.` instead of `Permission denied` — confirms /sandbox is writable |
| `grep -c 'github_pat_'` in worker logs (last 200 lines) | **0** — no token leak |
| `grep -c 'REDACTED:TOKEN'` in worker logs | **1** — redaction present |
| HGETALL on the job after re-run | `error` field contains `<REDACTED:TOKEN>`, no token |

## Verification caveat — the re-queued job still fails

The original job payload carries the repo as `"[chrporter22/insight-sys-website]"`
— including the literal square brackets. That is why the new error is
`Repository not found.` rather than a successful clone. This is a
**user-side typo**, not a worker bug. Re-running the same feature with
`/build chrporter22/insight-sys-website fix UI narrative so it's not
comparing A+ B` should now succeed end-to-end.

## What's uncommitted

```
 M core/bot/github_client.py
 M docker-compose.prod.yml
```

Suggested commit (the user runs this, not the agent):

```bash
git add core/bot/github_client.py docker-compose.prod.yml
git commit -m "Fix worker /sandbox tmpfs ownership + redact GITHUB_TOKEN from git error messages"
```

## Findings the next session should not re-diagnose

- **`/sandbox` ownership has to be set explicitly on the tmpfs mount.**
  Compose does not pick up the image's USER directive for tmpfs
  ownership. Either set `uid`/`gid` on the mount (this fix) or
  chown from an entrypoint running as root.
- **The token-leak path is now closed for git errors.** Future work
  that builds URLs with secrets should follow the same redaction
  pattern (`<SECRET>.replace(secret, "<REDACTED:SECRET>")` before
  raising). The pattern is captured in the code; no separate decision
  file written yet — can be added if/when another secret-bearing
  error path shows up.
- **Existing exposure to clean up.** The original failure left the
  token in `docker logs` (only the live log buffer; the dead-letter
  payload in Redis was overwritten by the re-queue test, which now
  contains `<REDACTED:TOKEN>`). The `.env` on disk still holds the
  real token, which is correct (gitignored, scoped to the host).
  Rotation remains the user's call — flagged but not performed.
- **`send_telegram` has its own try/except, so a placeholder
  `TELEGRAM_TOKEN` will not crash the worker on dead-letter
  notification.** Verified by reading `queue_worker.py:67-75`.

## On `LITELLM ESCALATE` / `LITELLM COMPACT`

Both are project-internal labels confirming LiteLLM is the gateway
tech and naming the `/chat` code path. They are not overrides of
plan-first, not separate operational modes, not new features.
Plan-first, single-agent, user-approval-before-implementation was
followed in this session as in the 2026-10-31 decision.
