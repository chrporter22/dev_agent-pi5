# Session: Dynamic AI gateway model + Telegram token redaction

**Date**: 2026-11-15
**Task**: Two failures surfaced from the worker logs after the previous
session's fixes:

1. Job `49a40f89-902e-4900-b2c2-e2af12748ae8` failed permanently:
   `Gateway returned HTTP 403: model 'coder-complex' is not available
   for this API key`. Root cause: `.env` had `AI_GATEWAY_MODEL=coder-complex`,
   which the API key wasn't authorised for.
2. `openclaw-bot` was logging `Polling error: … /bot9222980295:AAHH…
   /getUpdates …` — the `requests` library embeds the full URL (with
   the Telegram bot token) in `RequestException` messages, and the
   polling loop logged those messages verbatim.

## Diagnosis

### 1. Hardcoded model → token mismatch

`config.py` defaults `AI_GATEWAY_MODEL` to `"company-coder"`. The
user's `.env` overrode this to `"coder-complex"`, which the API key
was not authorised for. The static reference was the only way the
worker chose a model — there was no discovery step. Either the user
had to guess a model name that happened to be authorised, or the
gateway rejected everything.

### 2. Token in exception messages

`requests` raises `RequestException` whose string representation
includes the full URL. Telegram URLs embed the bot token
(`/bot<TELEGRAM_TOKEN>/sendMessage`). Every call site that caught
and logged such an exception leaked the token. Five call sites in
the bot image:

| File | Line | Symptom |
|------|------|---------|
| `core/bot/bot.py` | 475 | `print(f"Polling error: {e}")` |
| `core/bot/bot.py` | 49-52 | `send_message` had no try/except; exception propagated to a wider handler that logged it |
| `core/bot/queue_worker.py` | 70-75 | `print(f"Failed to send Telegram: {e}")` |
| `core/bot/telegram_sender.py` | 20-24 | `_send` had no try/except; same propagation problem |

## What was done

### Subtask 1 — Dynamic model discovery

`core/bot/ai_gateway_client.py`:

- Module-level cache: `_MODEL_CACHE = {"model": None, "fetched_at": 0.0}`
  with TTL `_MODEL_CACHE_TTL = 3600` seconds.
- New `_discover_gateway_model()` — calls
  `GET {AI_GATEWAY_BASE_URL}/v1/models` with the bearer key. Intersects
  the returned model IDs with `AI_GATEWAY_ALLOWED_MODELS` (the
  whitelist — already parsed in `config.py` but unused for selection).
  Returns the first match or `None` on any failure (timeout, non-200,
  malformed body, no intersection).
- New `_resolve_model()` — returns the cached model if fresh, calls
  discovery otherwise, falls back to `AI_GATEWAY_MODEL` env on
  discovery failure.
- `parse_instruction`, `chat`, `plan_changes` all switched from
  `AI_GATEWAY_MODEL` to `_resolve_model()`. The `chat(messages, model=…)`
  signature is preserved — an explicit model (from the user's `/model`
  command, validated against the whitelist in `bot.py`) still wins
  over the discovery result.

`.env.example`: documented that `AI_GATEWAY_MODEL` is now the
*fallback* (used only when discovery fails), and that
`AI_GATEWAY_ALLOWED_MODELS` is the whitelist the discovery intersects
with.

### Subtask 2 — Telegram token redaction

`core/bot/telegram_sender.py`:

- New helper `_sanitize_for_log(msg)` — replaces `TELEGRAM_TOKEN` with
  `<REDACTED:TOKEN>` anywhere it appears in the string. Returns `msg`
  unchanged if no token is present or `msg` is not a string.
- `_send(chat_id, text)` now wrapped in `try/except requests.RequestException`
  with a `timeout=10`, logging `_sanitize_for_log(str(e))` instead of
  the raw exception message.

`core/bot/bot.py`:

- Imported `_sanitize_for_log` alongside the existing `_chunk_send`.
- `send_message(chat_id, text)` — same try/except + sanitization
  treatment.
- Polling loop error log — `print(f"Polling error: {_sanitize_for_log(str(e))}")`.

`core/bot/queue_worker.py`:

- Imported `_sanitize_for_log`.
- `send_telegram(chat_id, text)` — `print(f"Failed to send Telegram:
  {_sanitize_for_log(str(e))}")`.

All three sites share one helper, so a future call site that needs
the same treatment can import it from `telegram_sender` without
duplicating the redaction logic.

### Subtask 3 — Rebuild + verify

| Check | Result |
|-------|--------|
| `python3 -m py_compile` on all four edited files | exit 0 |
| `docker compose up -d --build openclaw-bot openclaw-worker` | both rebuilt, both Started |
| Worker startup log | `Worker started (ai-gateway + git)...` |
| `_discover_gateway_model()` against the live gateway (in-container) | returned `company-coder` |
| `_resolve_model()` | returned `company-coder` (discovery hit) |
| `_sanitize_for_log` against a synthetic exception containing the real token | `<REDACTED:TOKEN>` present, raw token absent (`contains token? False`) |
| Token leaks in `docker logs openclaw-bot --tail 100` after rebuild | `0` hits of the live token |

## What's uncommitted

```
 M .env.example
 M core/bot/ai_gateway_client.py
 M core/bot/bot.py
 M core/bot/queue_worker.py
 M core/bot/telegram_sender.py
```

Suggested commit (the user runs this, not the agent):

```bash
git add .env.example core/bot/ai_gateway_client.py core/bot/bot.py core/bot/queue_worker.py core/bot/telegram_sender.py
git commit -m "Dynamic AI gateway model via /v1/models discovery + redact TELEGRAM_TOKEN from bot logs"
```

## Findings the next session should not re-diagnose

- **The user's existing `.env` still has `AI_GATEWAY_MODEL=coder-complex`.**
  The fix above means that line is now only consulted as a fallback
  when discovery fails. It does not need to be edited; the next
  `/build` should succeed with `company-coder` from discovery.
  Cleaning the stale line out of `.env` is recommended for hygiene
  but not blocking.
- **`_MODEL_CACHE` is process-local and per-worker.** Each container
  (bot and worker) does its own discovery. Discovery results are
  consistent because the whitelist intersection is deterministic.
- **Bot container is still failing DNS for `api.telegram.org`.**
  This is a separate network issue (`outbound_net` config or Pi DNS).
  The new `try/except` + sanitization in `bot.py` means the polling
  loop no longer spams `Max retries exceeded` to the log on every
  poll cycle — it logs once per exception and the URL is redacted —
  but the underlying DNS issue must be fixed for `/chat` to work.
  Out of scope for this change.
- **The redaction helper only covers `TELEGRAM_TOKEN` and `GITHUB_TOKEN`.**
  `AI_GATEWAY_API_KEY` and `REDIS_PASSWORD` would also leak if a
  `requests` call to those endpoints raised with the URL in the
  message. They are not in URLs the worker/bot calls today, so this
  is theoretical. If a future service calls the gateway or Redis
  over HTTP and propagates exceptions to logs, the same pattern
  applies: replace the credential with `<REDACTED:SECRET>` before
  logging.

## On `LITELLM ESCALATE`

Project-internal label confirming the `/chat` code path and LiteLLM
gateway tech per `.ai/decisions/llm/2026-10-31--litellm-escalate-interpretation.md`.
Not an override of plan-first. The session was planned (two
sub-decisions: discovery vs hardcoded; helper-based vs inline
redaction), approved by the user, then implemented and verified.
