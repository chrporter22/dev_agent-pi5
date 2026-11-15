# Session: JSON escape repair + markdown fence stripping in the gateway client

**Date**: 2026-11-15
**Task**: Job `52df659f-1034-452f-b659-c18c18ef5a90` failed permanently with
`Gateway returned malformed JSON (Invalid \escape: line 1 column 4985
(char 4984))`. The user asked to repair **this** repo only — the external
ai-gateway repo is explicitly out of scope and must not be touched.

Scope confirmed with the user before implementation:
- **Subtask 1** — repair invalid JSON escapes in the parser.
- **Subtask 2** — fix markdown fence stripping.
- `.env` must not gain a model line back. `AI_GATEWAY_MODEL` stays commented
  out. This repo is a thin shell: it sends the command to ai-gateway and lets
  the gateway own model routing.

## Diagnosis

Two distinct failures were in play.

### 1. Invalid `\escape` — the actual bug (this repo)

`json.loads` rejects a JSON string containing a backslash followed by a
character that is not a valid JSON escape. Models writing file content into
a JSON string (regexes, Windows paths, nested newlines) sometimes emit a
**single** backslash where JSON requires **two**:

| Model emits (JSON source) | JSON requires | `json.loads` |
|---|---|---|
| `"const r = /\d+/"` | `"const r = /\\d+/"` | `Invalid \escape` |
| `"backslash and space"` | `"backslash and space"` | `Invalid \escape` |
| `"a\u12 b"` | `"a\\u12 b"` | `Invalid \uXXXX escape` |

Confirmed against the **live** gateway, not just theory: a probe prompt
asking for "the literal two characters backslash and space" plus a regex
returned exactly this pattern, and the raw content was
`...content":"export const Test = () => {\\n  const literal = \\"\\\\\\\\
\\";\\n  const regex = /\\d+/;...` — one backslash where JSON needs two.

Note the failing offset (`char 4984`) is well past the 300-char response
head the error log prints, which is why the original error was hard to
diagnose from the log alone.

### 2. HTTP 403 `backup-minimax-m3` — upstream, not ours

The worker requested `company-coder` (confirmed: `_resolve_model()` →
`company-coder`; `GET /v1/models` → exactly one model, `company-coder`).
The 403 named `backup-minimax-m3`, a model name that appears **nowhere in
this repo** (`grep` over `core/` → zero hits) and is **not** advertised by
the gateway's `/v1/models`.

Direct probe from inside the worker container:

| Requested model | Result |
|---|---|
| `company-coder` | HTTP 200 |
| `backup-minimax-m3` | HTTP 403 `key_model_access_denied` |

The gateway serves the same model id from different upstream providers
across calls (`Wafer`, `GMICloud` observed) — it is routing/falling back
internally to a model the key cannot reach. That is an ai-gateway-side
configuration problem and was deliberately left alone per the user's
instruction.

Consequence for this repo: `_call_with_retry` re-sends an **identical** body
on every attempt, so a gateway-side flap re-rolls the dice each time. That
is why attempt 3 surfaced a different error than attempts 1-2. A
non-retryable 403 was raised immediately (`ai_gateway_client.py:224-225`).

**Conclusion:** the `Invalid \escape` failure is ours to fix; the 403 is
theirs. Subtasks 3 and 4 (served-model diagnostics, non-retryable-403
policy) were proposed but **excluded by the user** — only 1 and 2 were
implemented.

## Implementation

### Subtask 1 — `_repair_json_escapes` (`core/bot/ai_gateway_client.py`)

A single left-to-right scan of the raw text that rewrites only backslashes
JSON would read as invalid:

- `\` + a valid escape char (`"`, `\`, `/`, `b`, `f`, `n`, `r`, `t`) → left
  untouched.
- `\u` + exactly 4 hex digits → left untouched.
- `\u` without 4 hex digits → the backslash is escaped literally.
- `\` + anything else → the backslash is escaped literally.
- trailing lone `\` → escaped literally.

**Semantics: the backslash is preserved, never dropped.** Dropping it would
silently corrupt the file the model was writing — a regex `\d+` would
become `d+`. The repair is escape-aware, not a blanket replace, so
already-valid content is bit-for-bit unchanged.

Applied in `_safe_parse_json` as a **fallback**: parse first, and only if
that raises `JSONDecodeError` do we attempt the repair and re-parse. Well
-formed responses take the fast path and are never rewritten.

### Subtask 2 — `_strip_code_fence` (same file)

The old code did `"\n".join(lines[1:-1])`, which unconditionally dropped the
**last** line. With prose after the closing fence, that left the fence and
the prose in the text and the parse failed with `Extra data`. The new
helper walks the body lines and cuts at the **first** line that starts a
fence, so anything after the closing fence is discarded too.

### `.env.example` — `AI_GATEWAY_MODEL` commented out

The live `.env` already had `AI_GATEWAY_MODEL` commented out, but
`.env.example` (the template that gets copied to `.env`) still had it
**uncommented**. Left as-is, the next environment setup would silently
re-introduce a hardcoded model. Now commented out to match, with the
comment block updated to explain the dynamic discovery flow and the
thin-shell rule.

## Verification

Run inside the rebuilt worker container (host has no `requests`; the
Docker-only rule applies).

| Check | Result |
|---|---|
| `python3 -m py_compile core/bot/ai_gateway_client.py` | exit 0 |
| Worker rebuilt (`docker compose -f docker-compose.prod.yml up -d --build openclaw-worker`) | Started, healthy |
| `_safe_parse_json` on single-escaped backslash-space | parses |
| `_safe_parse_json` on single-escaped regex `/\d+/` | parses |
| `_safe_parse_json` on lone `\u12` | parses |
| `_safe_parse_json` on already-valid escapes (`\n`, `\"`, `\d+`, `\u00e9`) | unchanged — no double-escaping |
| Content fidelity | decoded content contains literal backslash+space and `\d`; backslash preserved |
| Fence: trailing newline / no trailing newline / prose after / bare fence / no fence | all parse to `{"files": []}` |
| Live gateway probe (the previously-failing prompt) | raw `json.loads` FAILED on the same pattern; `_safe_parse_json` parsed it |
| Repaired content fidelity | file written to disk contains `"\\ "` and `/\d/` — exactly as intended |
| Full job through the queue (`test-escape-fix-0002`) | `Job complete: test-escape-fix-0002` |
| PR | opened on the target repo, branch `dev-agent/test-esc` |
| Token leak check (worker + bot logs) | 0 hits for the GitHub token, Telegram token, and gateway API key |

### Test artifact cleanup

The verification job created real artifacts on the target repo. All were
removed:

- PR #4 closed via the GitHub API.
- Branch `dev-agent/test-esc` deleted via the GitHub API (HTTP 204).
- Test job records removed from Redis (`jobs:complete`, `jobs:failed`,
  `jobs:running`, `queue:dead` all back to 0).

## Findings the next session should not re-diagnose

- **The `backup-minimax-m3` 403 is upstream and still open.** The gateway
  routes internally to a model our key cannot reach. The user confirmed the
  API key is correct and asked that the ai-gateway repo not be touched, so
  it remains an ai-gateway-side fix. Note the api-gateway repo lives
  **outside** this repo (`~/ai-gateway`) — nothing in `core/` references it.
- **`AI_GATEWAY_MODEL` is now commented out in both `.env` and
  `.env.example`.** `config.py:14` still defaults it to `company-coder`,
  so `_resolve_model()`'s fallback path works without any env var set.
- **Redis has no persistence volume.** The compose `--build` recreated the
  `redis` container (its generated ACL file changed), which wiped the job
  queue and `jobs:*` sets. A `docker compose up --build` can therefore
  silently reset in-flight job state. Worth knowing before debugging a
  "missing" job.
- **`user default off` in `redis/users.acl.template`** — there is no admin
  Redis user, by design. To inspect job state, authenticate as `bot` or
  `worker` using their own passwords from the container env. The `worker`
  ACL grants `~chat:* ~queue:* ~job:* ~jobs:* ~worker:*` with `+@all`
  minus destructive commands.
- **`DEFAULT_REPO` is empty in `.env`.** A build job without an explicit
  `repo` fails with `No repo specified`. Job payloads must carry
  `"repo": "owner/repo"`.
- **The `Invalid \escape` error message truncates the response head at 300
  chars**, so the actual offending offset (e.g. char 4984) is not visible
  in the log. Reproducing with a targeted probe prompt is what made this
  diagnosable.

## On LITELLM COMPACT / LITELLM ESCALATE

Project-internal labels marking the `/chat` code path and LiteLLM gateway
tech per `.ai/decisions/llm/2026-10-31--litellm-escalate-interpretation.md`.
Not urgency flags and not plan-first overrides. The session was planned,
scope was narrowed by the user to subtasks 1 and 2, and the work was
approved before implementation.
