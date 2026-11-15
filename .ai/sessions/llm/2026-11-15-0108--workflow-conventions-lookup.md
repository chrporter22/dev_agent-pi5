# Session: Dynamic repo-convention lookup for /build workflow generation

**Date**: 2026-11-15
**Task**: Fix hallucinated `.github/workflows/*.yml` on bot PRs by making
the worker read the target repo's `AGENTS.md`, `CLAUDE.md`, `.ai/decisions/`,
`.ai/sessions/`, and existing `.github/workflows/` before calling
`plan_changes()`. Delete the broken PR. Verify helpers in-container.

## Diagnosis

Job `285328e9-0364-4bd5-8c57-01db16ba13f3` on
`chrporter22/insight-sys-website` opened PR #1. The PR contained a
`.github/workflows/build-and-test.yml` that referenced paths that don't
exist in the target repo (`apps/web`, `apps/api`, `apps/admin`,
`apps/quotes`, `npm ci`, `npm test` per app). GitHub Actions failed every
step.

Root cause was in two places:

1. **`_gather_repo_context()`** (queue_worker.py:133) returned only
   `{files, language}` — a sorted filename list capped at 200 and a
   language string inferred from extensions. It never read `AGENTS.md`,
   `CLAUDE.md`, `.ai/decisions/`, `.ai/sessions/`, or existing
   `.github/workflows/*.yml`, so the gateway had zero visibility into
   the target repo's conventions.

2. **`PLAN_CHANGES_SYSTEM_PROMPT`** (ai_gateway_client.py:62-79)
   contained the bullet:
   > When adding new code, also include a .github/workflows/<name>.yml
   > file that builds Docker images and runs unit tests.

   Combined with (1), this told the gateway to always invent a
   Docker+test workflow with no information about what the repo
   actually contained. Hence the hallucinated monorepo shape.

## What was done

### Subtask 1 — Deleted the broken PR

GitHub API via `curl` with the worker's `GITHUB_TOKEN`:

- `PATCH /repos/chrporter22/insight-sys-website/pulls/1`
  → `state=closed merged=False`
- `DELETE /repos/chrporter22/insight-sys-website/git/refs/heads/dev-agent/285328e9`
  → HTTP 204 (head branch removed)

User authorized deletion without merge.

### Subtask 2 — `_gather_repo_context()` now returns `conventions`

`core/bot/queue_worker.py`:

- Added `from typing import Any, Dict, Optional` to the imports.
- `_gather_repo_context()` now includes a third key:
  `"conventions": _gather_conventions(sandbox_dir)`.
- New helper `_read_capped(path, limit)` — returns first `limit` chars of
  a file, or `None` on `FileNotFoundError` / `IsADirectoryError` /
  `PermissionError` / `OSError`.
- New helper `_gather_ai_index(sandbox_dir, sub, max_files)` — walks
  `.ai/<sub>/` and returns `{filename: first_line_of_file}` for up to
  `max_files` files. Returns `{}` if the directory is missing.
- New helper `_gather_workflows(sandbox_dir)` — walks
  `.github/workflows/` and returns `{filename: full_content}` for every
  `*.yml` / `*.yaml` file (capped at 4096 chars each). Returns `{}` if
  the directory is missing.
- New helper `_gather_conventions(sandbox_dir)` — returns the dict:
  ```
  {
    "agents_md":    str | None,   # first 4096 chars of AGENTS.md
    "claude_md":    str | None,   # first 4096 chars of CLAUDE.md
    "ai_decisions": {file: first_line},   # up to 10
    "ai_sessions":  {file: first_line},   # up to 5
    "workflows":    {file: content},      # every *.yml/*.yaml
  }
  ```

Capping strategy: AGENTS.md/CLAUDE.md are truncated at 4KB to protect
the gateway's token budget (`AI_GATEWAY_MAX_TOKENS=8000` by default).
`.ai/` entries carry only filename + first line, because the target repo's
session history is not what the gateway needs — it needs to know the files
*exist* so it knows the convention source is present. Workflow files are
kept in full because they are small and are the actual pattern to follow.

### Subtask 3 — `PLAN_CHANGES_SYSTEM_PROMPT` uses the conventions

`core/bot/ai_gateway_client.py:PLAN_CHANGES_SYSTEM_PROMPT` — three new
bullets added, one existing bullet rewritten:

- The `conventions` field is now named in the prompt so the gateway knows
  what to look for.
- New bullet: only reference paths that appear in the `files` list or
  that you are creating in this change. Never invent paths.
- Rewritten workflow bullet: if the repo has `.github/workflows/*.yml`,
  extend or modify an existing one following its style. If it has none,
  create one matching the repo's actual structure — derive build/test
  commands from `files` and `conventions`, not from assumptions.

The output JSON shape `{files: [{path, action, content}]}` is unchanged.
No change to `_apply_changes()`, `_format_pr_body()`, or the PR flow.

### Subtask 4 — Rebuild and verify

| Check | Command / method | Result |
|-------|------------------|--------|
| Python syntax | `python3 -m py_compile core/bot/queue_worker.py core/bot/ai_gateway_client.py` | exit 0 |
| Rebuild worker | `docker compose -f docker-compose.prod.yml up -d --build openclaw-worker` | built + Started |
| Worker startup log | `docker logs openclaw-worker --tail 5` | `Worker started (ai-gateway + git)...` |
| Synthetic repo smoke test | `_gather_repo_context('/tmp/smoke')` inside the worker container against a fake sandbox containing `AGENTS.md`, `CLAUDE.md`, `.ai/decisions/2026-01-01--test.md`, `.ai/sessions/2026-01-01--test.md`, `.github/workflows/ci.yml`, `core/app.py` | All five convention fields populated: `agents_md='AGENTS rule content here\n'`, `claude_md='CLAUDE rule\n'`, `ai_decisions={'2026-01-01--test.md': '# decision file one'}`, `ai_sessions={'2026-01-01--test.md': '# session file one'}`, `workflows={'ci.yml': 'name: CI\non: [push]\n…'}`. `language='python'`, `files` contains all 5 paths. |

## What's uncommitted

```
 M core/bot/ai_gateway_client.py   (+16/-1)
 M core/bot/github_client.py       (+10/-1)   # earlier redaction fix
 M core/bot/queue_worker.py        (+77/-1)
 M docker-compose.prod.yml         (1-line)    # earlier /sandbox fix
?? .ai/sessions/llm/2026-11-15-0034--worker-sandbox-and-token-redaction.md
?? .ai/sessions/llm/2026-11-15-0108--workflow-conventions-lookup.md   (this file)
```

Suggested commit (the user runs this, not the agent):

```bash
git add \
  core/bot/ai_gateway_client.py \
  core/bot/github_client.py \
  core/bot/queue_worker.py \
  docker-compose.prod.yml \
  .ai/sessions/llm/2026-11-15-0034--worker-sandbox-and-token-redaction.md \
  .ai/sessions/llm/2026-11-15-0108--workflow-conventions-lookup.md

git commit -m "Read target repo conventions before generating /build changes + fix worker /sandbox + redact GITHUB_TOKEN"
```

## Findings the next session should not re-diagnose

- **The hallucinated workflow prompt bullet is gone.** The old
  `PLAN_CHANGES_SYSTEM_PROMPT` bullet that told the gateway to always
  invent a Docker+test workflow has been replaced. If a future session
  sees a hallucinated workflow again, the root cause is elsewhere (e.g.
  gateway not receiving `conventions`, or a different prompt).
- **The `.ai/` in the target repo is *referenced, not read in full*.**
  The worker returns only `{filename: first_line}` for up to 10
  decision files and 5 session files. It does not read every byte of
  session history — both to protect the token budget and to avoid
  leaking the target repo's private work history wholesale into the
  prompt.
- **`_read_capped()` swallows `OSError`.** This is deliberate — the
  target repo may have a `AGENTS.md` that is a directory (weird but
  possible on some systems), unreadable file, or symlink to nowhere.
  None of these should crash the build; returning `None` lets the
  gateway adapt.
- **Worker image does NOT contain the dev repo's own `.ai/`, `AGENTS.md`,
  or `.github/workflows/`.** The worker `Dockerfile` `COPY . .` only
  copies `core/bot/`. So a smoke test of `_gather_repo_context('/app')`
  inside the worker returns empty conventions. To verify against real
  convention files, create a synthetic sandbox under `/tmp` inside the
  container. This is expected, not a bug.
- **PR #1 on `chrporter22/insight-sys-website` was closed and its head
  branch deleted.** Not merged. Clean slate for the next `/build` run.