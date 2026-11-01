# LEAVE-OFF — Phase 5 shipped; awaiting user integration

- **Date:** 2026-10-31 (post-0008, mid-evening iteration)
- **Topic:** llm
- **Sess ID:** 2026-10-31-0009 (continuation of 2026-10-31-0008)
- **Status:** Phases 1–5 ✅ shipped in code. Wiring to live gateway is on the user.

## What this session changed

### Phase 5 artifacts created (NEW, uncommitted on the working tree)

| File | What it is |
|------|-----------|
| `.github/workflows/build-pr.yml` | Template workflow for target repos — PR-triggered Docker build + unit tests via the new composite action. The bot's `PLAN_CHANGES_SYSTEM_PROMPT` instructs the gateway to drop this file (renamed) into target repos via `plan_changes`. |
| `.github/actions/docker-build/action.yml` | Reusable composite action: build + optional push, with GHA cache. Inputs: `service`, `context`, `push`, `tags`, `cache-from`, `cache-to`. Used by `build-pr.yml` (push:false) and could be used by `deploy.yml` (push:true) in a future refactor. |
| `.ai/decisions/llm/2026-10-31--lightweight-vertical-to-ai-gateway.md` | Decision record for the bot ↔ gateway integration contract. Headline: OpenAI-compat `/v1/chat/completions`, bearer auth, three system-prompt patterns over one endpoint, **no gateway-side facade, no bot-side OpenAPI spec**. The ai-gateway repo just needs LiteLLM default config + reachability from this stack. |

### Phase 5 doc flips (MODIFIED, uncommitted)

- `README.md` — Phase 5 row flipped ⏳ → ✅ (line 362). Roadmap now shows all 5 phases complete.
- `PRD.md` — three flips: header status line, non-goals "CI/CD in this repo" entry, and Phase 5 row in §13 roadmap.

### Verified

- YAML syntax valid for all 4 new YAML files (ci, deploy, build-pr, action).
- Action schema correct (`runs.using: composite`, required inputs present).
- Secret scan clean on new files (`sk-…`, `ghp_…`, `AKIA…`, `xox…` patterns).
- Git status clean apart from the 5 intended uncommitted files.

### What was NOT changed

- `docker-compose.prod.yml` — no new services. Phase 5 is repo-local tooling, not a new container.
- `ai_gateway_client.py` — unchanged. The integration decision ratifies what's already there.
- `core/bot/`, `core/ml/`, `core/node-api/`, `core/pca-backend/` — untouched in this iteration.

## What's uncommitted (handoff to user)

```
?? .ai/decisions/llm/2026-10-31--lightweight-vertical-to-ai-gateway.md
?? .github/actions/docker-build/action.yml
?? .github/workflows/build-pr.yml
 M PRD.md
 M README.md
```

Suggested commit:

```bash
git add \
  .ai/decisions/llm/2026-10-31--lightweight-vertical-to-ai-gateway.md \
  .github/actions/docker-build/action.yml \
  .github/workflows/build-pr.yml \
  README.md \
  PRD.md

git commit -m "Phase 5: CI/CD workflows + bot-gateway integration decision"
git push
```

## User-side tasks (not code, not on the agent)

The repo is shippable. The integration with a live LiteLLM gateway + Telegram bot is on the user:

| # | Task | How |
|---|------|-----|
| 1 | Create Telegram bot | `@BotFather` → `/newbot` → copy token to `TELEGRAM_TOKEN` |
| 2 | Get Telegram user ID | `@userinfobot` or `@getidsbot` → copy numeric ID to `ALLOWED_USER` |
| 3 | Generate per-service Redis passwords | `openssl rand -hex 32` → fill `REDIS_PASSWORD_BOT/WORKER/ML/NODEAPI` |
| 4 | Generate GitHub fine-grained PAT | github.com → Settings → Developer settings → PATs (classic) with `repo` scope, or fine-grained with `contents:write` + `pull_requests:write` on target repos → `GITHUB_TOKEN` |
| 5 | Stand up LiteLLM gateway | In `~/ai-gateway`: `LITELLM_MASTER_KEY=<key> litellm --port 4000` (or whichever invocation the gateway repo uses) |
| 6 | Wire gateway URL + key into `.env` | `AI_GATEWAY_BASE_URL=http://host.docker.internal:4000` (or LAN IP), `AI_GATEWAY_API_KEY=<key>`, `AI_GATEWAY_MODEL=<model the gateway has>` |
| 7 | Deploy | `cp .env.example .env && docker compose -f docker-compose.prod.yml up -d --build` |
| 8 | Smoke test | `docker exec openclaw-worker python -c "from ai_gateway_client import chat; print(chat([{'role':'user','content':'reply pong'}]))"` → expect `pong` |
| 9 | First real test | In Telegram, message the bot `/chat hello` → expect a reply. Then `/build owner/repo add a README section` → expect a PR URL. |

If step 8 fails, debug path is in the decision file §"How to verify" — check `docker logs openclaw-worker` for the HTTP status code the gateway returned.

## Open threads (not blocking ship)

- **`.ai/index/` not built.** The `repo-index` skill is installed but the index itself isn't. ~70 source files would each get a per-file entry, plus `toc.md`, `modules.md`, `symbols.md`, `graph.json`. Adds a maintenance obligation on every file change. Defer until someone notices a navigation pain.
- **`parse_instruction()` in `ai_gateway_client.py` is unused.** Currently kept for a future `/plan` command. Safe to delete if it stays unused for one more release; cheaper to keep until then. Decision deferred.
- **`.gitignore` hygiene** — already fixed this session (added `node_modules/` + `package-lock.json`). Other stale entries exist (`core/llm/*.gguf`, `db.sqlite`, `index.bin`, `.terraform/`) from the deleted `core/llm` and `core/vdb` services but they don't cause noise and aren't worth a bundled cleanup commit.
- **`build-pr.yml` matrix references `./core/<service>` paths.** That assumes the target repo mirrors this repo's layout. If the bot is being used against a repo with a different layout, the template will need per-target customization — which is fine because the bot's `plan_changes` will rewrite it.
- **Decision file `.ai/decisions/llm/2026-10-28--lightweight-vertical-to-ai-gateway.md`** — the LEAVE-OFF plan called for this exact path, but the file was written with the actual session date `2026-10-31` instead. The decision file references the older path under "Supersedes / relates to" as `2026-10-28--lightweight-vertical-to-ai-gateway.md`. If you want to preserve the LEAVE-OFF naming, rename the file. Otherwise the discrepancy is benign (the file's content is the same as what was intended).

## No pending code work

Phases 1–5 are all ✅ in code. The repo is shippable as-is. Anything beyond user-side setup and the open threads above is a deliberate new initiative, not a continuation.

## Relates to

- `.ai/sessions/llm/2026-10-31-0008--review-leave-off-and-plan.md` — the parent session that did Phases 1–4 + skills audit + README/PRD build.
- `.ai/sessions/llm/2026-10-28-2053--LEAVE-OFF.md` — original 17-subtask plan. Phase 5 items 1–6 (workflows + action + decision file + verification + roadmap flips) are now all closed.
- `.ai/decisions/llm/2026-10-31--lightweight-vertical-to-ai-gateway.md` — the new Phase 5 decision record.
- `.ai/decisions/llm/2026-10-19--replace-local-qwen-with-litellm.md` — the original "use LiteLLM" decision that this builds on.
- `.ai/decisions/llm/2026-10-31--litellm-escalate-interpretation.md` — `LITELLM ESCALATE` / `LITELLM COMPACT` / `LITELLM EXECUTE` label semantics. None of them are operational overrides.
