# Session: Validate /build repo arg against embedded whitespace

**Date**: 2026-11-15
**Task**: User reported "failed token" from Telegram. Diagnose and fix.

## Diagnosis

The dead-letter payload for `95e112c6-5837-4e4a-a2a4-0f23b5f14ed5` showed:

```
'repo': 'chrporter22/insight-sys-\n\nReview'
```

The user's `/build` message had a paste that put `Review` on its own line.
`text.split(" ", 2)` produced `parts[1] = "chrporter22/insight-sys-\n\nReview"`.
`parts[1].strip()` only trims edges, so embedded `\n` survived and reached
`queue_build`. The worker built the clone URL
`https://x-access-token:<TOKEN>@github.com/chrporter22/insight-sys-\n\nReview.git`,
git returned `credential url cannot be parsed`, the job failed permanently,
and the user saw "failed token" in Telegram.

`GITHUB_TOKEN` itself was clean (93 chars, no newline, hex-verified).
`DEFAULT_REPO` was empty in `.env`. The failure was not token-related — it
was an unsanitized user input.

## Fix

In `core/bot/bot.py:369-378`, validate the repo arg against
`[A-Za-z0-9._/-]+` before queueing. If it contains whitespace, reply with
a usage hint and do not queue.

```python
elif len(parts) >= 3 and "/" in parts[1]:
    repo_arg = parts[1].strip()
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", repo_arg):
        send_message(
            chat_id,
            "Repo must not contain whitespace; send "
            "/build owner/repo <feature> on one line."
        )
        return
    queue_build(chat_id, repo_arg, parts[2].strip())
```

Added `import re` at the top.

## Verification

- `docker compose -f docker-compose.prod.yml build openclaw-bot` — built clean
- Redeployed `openclaw-bot` and `openclaw-worker` together (worker image
  unchanged but recreated to start the fresh worker loop)
- Worker logs: `Worker started (ai-gateway + git)...` then idle on `brpoplpush`
- Regex smoke-test in Python: clean repo passes, embedded `\n\n` rejected,
  embedded space rejected, trailing `\n` already stripped before regex
- No new jobs in queue; no leftover retries

## What this session did NOT do

- Did not rotate `GITHUB_TOKEN`. The token is good.
- Did not modify `DEFAULT_REPO` in `.env`. It stays empty.
- Did not touch `core/bot/queue_worker.py` or `core/bot/github_client.py`.
  The clone path is correct; the input is the issue.
- Did not change any of the Phase 3/4 fixes or Redis ACL rules.
