# No API keys in frontend; RLS in any database

- **Date:** 2026-10-28
- **Decided by:** user (chat, this session)
- **Topic:** security

## Decision

Two project-wide security principles are now in force:

1. **No API keys in any frontend.** Every secret (third-party API key, bearer token, GitHub token, Telegram bot token, Redis password, gateway key) lives only in env on a backend service. Frontends — the Telegram bot (input surface), the PCA dashboard (output surface), and any future UI — never embed, receive, or persist a secret. The Telegram bot's own token is the only exception, because it is the bot's identity, not a third-party credential.
2. **Row-Level Security on any database.** If a SQL database is added (Postgres, SQLite with row security, etc.), RLS policies must be enabled from day one. No service gets blanket table access. For Redis (the current store), the equivalent is per-service ACLs with key-pattern permissions rather than a single shared password.

## Why

- The Telegram bot is a public input surface. Any secret embedded in it could be extracted by an attacker who compromises the bot's logs, image, or container.
- The PCA dashboard is the only public egress (port 80). It must never hold a key that, if leaked, would compromise a backend service.
- A single shared Redis password is a blast radius problem. Per-service ACLs limit what each compromised service can see or mutate.
- RLS is much cheaper to enable from day one than to retrofit after data has accumulated.

## What stays

- All secrets continue to flow through env (`os.getenv` in Python, `process.env` in Node, `${VAR}` interpolation in compose).
- `.env` is gitignored. `.env.example` carries placeholders only.
- The Telegram bot holds its own `TELEGRAM_TOKEN` (this is the bot's identity, not a third-party credential).
- Redis currently uses a single `REDIS_PASSWORD` (works today; the per-service ACL upgrade is on the roadmap but is not blocking).

## What changes

- New rule: any new frontend must declare its secret-free posture in its README and any future PR review must reject embedded keys.
- New rule: any future SQL service ships with RLS policies in its first migration, not later.
- New rule: Redis ACL tightening is on the roadmap; when it ships, each service gets its own user with the minimum key-pattern access it needs.

## Enforcement (current state, audited 2026-10-28)

- No hardcoded API keys found in tracked source (verified by grep for `sk-…`, `ghp_…`, `AKIA…`, `xox[baprs]-…` patterns — zero hits).
- All secret references in source are env reads (`os.getenv` in `core/bot/config.py`, `os.getenv` in `core/ml/...`, env interpolation in `docker-compose.prod.yml`).
- `.env.example` uses placeholders (`your_telegram_bot_token_here`, `ghp_replace_me`).
- `.env` is in `.gitignore` and not tracked.
- The PCA dashboard (`core/pca-backend/`) holds zero secrets; it only proxies to `core/node-api`.
- `core/node-api/` holds only `REDIS_HOST`/`REDIS_PORT` in its compose env block; no third-party keys.

## Deferred to user

- Concrete Redis ACL split (one user per service with key-pattern allowlists). Worth doing; not blocking.
- A future SQL service would need RLS policies written as part of its first migration.
- An automated secret-scan hook (gitleaks / trufflehog) on commits. Worth doing; not blocking.

## Supersedes / relates to

- Reinforces the security posture documented in `AGENTS.md` "Persistence and Ops" section (AES-256-GCM encryption at rest, env-only secrets) and the project-specific rule "Secrets come from env only".
- Pairs with `.ai/decisions/llm/2026-10-19--replace-local-qwen-with-litellm.md` — when the local LLM was removed, all inference was routed through the gateway with bearer auth in env only; this decision formalizes that pattern as a project rule.
- Pairs with `.ai/decisions/simplify/2026-10-24--strip-llm-and-vdb-keep-bot-pca.md` — when vdb/SQLite was removed, this repo stopped having any SQL surface; if SQL returns (it shouldn't), RLS is the price of admission.
