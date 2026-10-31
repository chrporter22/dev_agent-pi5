# LITELLM ESCALATE — interpretation and security confirmations

- **Date:** 2026-10-31
- **Decided by:** user (chat, this session)
- **Topic:** llm

## Decision

`LITELLM ESCALATE` (and the related project-internal labels `LITELLM COMPACT`, `LITELLM EXECUTE`) is the name for the Telegram `/chat` code path: a user sends `/chat <text>`, the bot forwards the message plus chat history to the external `~/ai-gateway` LiteLLM endpoint, the gateway returns suggestions, and the bot replies via Telegram. The label confirms the gateway tech (LiteLLM) — it is not an override of the plan-first rule, not a separate operational mode, and not a new feature.

## Why

User clarified the label in chat today. The interpretation aligns with the planned `/chat` workflow in `.ai/sessions/llm/2026-10-28-2053--telegram-dictation-and-ai-gateway-review.md`.

## Security confirmations (reaffirmed 2026-10-31)

- **No API keys in any frontend.** Bot, dashboard, and any future UI hold zero third-party credentials. All secrets flow through env on a backend service. Already the rule (`.ai/decisions/security/2026-10-28--...md`).
- **If SQLite is added later, build it from binary.** Hardening stance: do not rely on a precompiled SQLite DB blob; build the SQLite engine and schema from a controlled binary source. RLS policies must be enabled from day one (same decision).
- **Redis cache zero-trust posture.** No root access to host, RBAC procedures followed, and access limited to a specific user identified by the Telegram token. Today this is realized via the `ALLOWED_USER` single-ID gate on all bot commands (`core/bot/bot.py:167`). Per-service Redis ACLs with key-pattern permissions are the next-level refinement and remain on the roadmap (same security decision, "Deferred to user").

## What stays

- The existing `ALLOWED_USER` gate on the bot is the per-user RBAC enforcement.
- `.env` is gitignored. `.env.example` carries placeholders.
- All containers run `read_only: true` with `cap_drop: ALL`, `no-new-privileges`. Worker adds a `SANDBOX_DIR=/sandbox` tmpfs (Phase 3).

## What changes

- Nothing structural. This file documents the interpretation and reaffirms the security stance already in force. The `/chat` command ships in Phase 2 of the implementation plan (subtask 6 of 17).

## Supersedes / relates to

- `.ai/decisions/security/2026-10-28--no-api-keys-in-frontend-rls-in-database.md` — the security baseline.
- `.ai/sessions/llm/2026-10-28-2053--LEAVE-OFF.md` lines 268-270 — the prior placeholder paragraph ("project-internal label"); this decision replaces it.
- Phase 2 of the implementation plan — adds `/chat` (and `/clear`, `/model`) to `bot.py`.
