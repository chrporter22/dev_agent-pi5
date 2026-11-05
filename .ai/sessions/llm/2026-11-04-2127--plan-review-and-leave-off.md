# Plan review and leave-off point

- **Date:** 2026-11-04 21:27
- **Developer:** opencode (company-coder)
- **Topic:** llm

## Request

User asked for a review of the current plan and the leave-off point, plus next steps. The
`LITELLM ESCALATE` marker is the upstream tier-routing hint and carries no instruction to the
agent (per `.ai/decisions/llm/2026-10-31--litellm-escalate-interpretation.md`).

## What was done

Review only — no code, config, or doc files changed. Read the decision history and the four most
recent session files, then re-verified the live state of the running stack instead of trusting
the session notes.

### Plan state

Phases 1–5 are all marked shipped in both `README.md` and `PRD.md` §13. There is no Phase 6
defined anywhere. The plan of record is `.ai/sessions/llm/2026-10-28-2053--LEAVE-OFF.md` plus the
five phase flips in `.ai/sessions/llm/2026-10-31-0008--review-leave-off-and-plan.md`.

### Leave-off point

The last commit is `a3f1152` "add final touches before deloyment" (2026-10-31 23:22). It contains
the nginx → Node http server swap, the bring-up README, the bot command table, and the memory
files. `origin/main` is at the same commit; the tree is clean. The stated leave-off was "repo is
shippable; remaining work is user-side setup".

### Live state re-verified (2026-11-04)

Working:

- All six containers are up. Redis, worker, and dashboard report healthy.
- The gateway path works end to end: a live `chat()` call from inside `openclaw-worker` returned
  `pong`. Model `company-coder`, virtual key, base URL on the gateway orchestrator.
- The dashboard UI answers 200 on `/`, and the read-only ML API answers 200 on
  `/api/ml/pca/summary`, `/api/ml/drift`, `/api/ml/risk` through the Node proxy.
- DNS and TLS to `api.telegram.org` work from inside the bot container.

Blocked:

- `TELEGRAM_TOKEN` in `.env` is still the literal placeholder. A live `getMe` against Telegram
  returns HTTP 404 `{"ok":false,"error_code":404}`. The bot cannot work end to end until a real
  BotFather token is supplied.
- `ALLOWED_USER` is `0`. That denies every user, which is the deliberate fail-closed setting, but
  it also means the bot stays silent even once the token is real.
- The ML pipeline is still dormant — `core/ml` logs "No data source wired -- pipeline idle" on
  every cycle. The dashboard therefore has nothing to display. This is the largest functional gap
  in the product and it is the only open item from the roadmap that needs engineering rather than
  a user-supplied secret.

## Notable findings

- The bot's polling errors (`Connection reset by peer`) are not a network problem. TCP and TLS to
  `api.telegram.org` succeed from the container; the failure is the placeholder token, which
  Telegram answers with 404 on every long-poll request.
- The `README.md` "Out of scope" section still lists "Phase 5 CI — pending" while the roadmap two
  sections above says Phase 5 shipped. `PRD.md` §12 has the corrected wording. Stale line in
  `README.md`.
- `AGENTS.md` "Known-broken" list is accurate as of the last commit, but its `core/ml` entry
  (data source unwired) is the same dormant-pipeline gap seen from the product side.

## Open threads

- No code changes made in this session except one README doc edit (see below).
- Candidate next-step buckets, in the order they unblock the product:
  1. Wire a data source into `core/ml` so PCA, drift, and risk produce real numbers and the
     dashboard stops rendering empty state.
  2. User-side secrets (BotFather token, allowed user id) — needed for any live Telegram test.
  3. Doc and memory hygiene: stale Phase 5 line in `README.md`, the `.ai/index/` build that was
     deferred, the unused `parse_instruction()` in the bot client.
- The gateway-side follow-ups (`scripts/create-dev-key.sh` minting a slash-separated model name
  that 403s, a distinct `application_id` for bot traffic) live in `~/ai-gateway` and are out of
  scope for this repo.
- **README.md:79** — added `/chat hello` to the Bring-up step 5 smoke test. The existing text
  only exercised `/status` and `/help`; the new line makes the user verify the full
  Telegram→worker→gateway path before considering bring-up complete.
