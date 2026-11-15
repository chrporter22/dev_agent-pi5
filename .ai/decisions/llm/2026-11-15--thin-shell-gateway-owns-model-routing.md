# This repo is a thin shell: the gateway owns model routing

- **Date:** 2026-11-15
- **Decided by:** user (chat, this session)
- **Topic:** llm

## Decision

`dev_agent-pi5` sends commands to `ai-gateway` and lets the gateway decide which model serves
them. This repo does **not** hardcode a model name, and `AI_GATEWAY_MODEL` stays commented out in
both `.env` and `.env.example`.

Concretely:

1. **Model selection is dynamic, resolved at request time.** The worker calls
   `GET {AI_GATEWAY_BASE_URL}/v1/models` with its virtual key, intersects the returned model ids
   with the `AI_GATEWAY_ALLOWED_MODELS` whitelist, and uses the first match. The result is cached
   for one hour. `AI_GATEWAY_MODEL` exists only as a fallback for when discovery fails (gateway
   down, key rejected, `/v1/models` not exposed) and is not set in a normal environment.
2. **The gateway's internal routing is the gateway's problem, not ours.** When the gateway served
   a model our key could not reach (`backup-minimax-m3`, HTTP 403 `key_model_access_denied`), the
   correct place to fix it was the gateway repo. The user explicitly ruled that repo out of scope
   for that task: repair *this* repo, do not touch `ai-gateway`.
3. **The `/model` override stays available but whitelist-gated.** A per-chat model chosen via the
   Telegram `/model` command is validated against `AI_GATEWAY_ALLOWED_MODELS` before it is stored,
   so a user can never make the bot request a model the gateway does not expose.

## Why

The repo's value is the Telegram → branch → PR flow, not LLM inference. The gateway already owns
routing, decision logging, tier routing, and spend attribution; a second opinion about which model
to use inside the bot would duplicate that logic in the wrong place and would drift from whatever
the gateway decides. Keeping the bot thin also means a routing or model-authorisation change on
the gateway side needs no change here at all.

The `.env.example` case is the sharp one. The live `.env` had `AI_GATEWAY_MODEL` commented out, but
the template still had it uncommented — and `.env.example` is what gets copied to `.env` on a new
environment. Left alone, the next setup would silently reinstate the hardcoded model and the
discovery path would never run. Template and live env now agree.

Keeping the env var commented also documents the intent for the next reader: the absence of a
model name is deliberate, not an oversight.

## What this decision does not cover

- **The gateway-side 403 is still open.** `backup-minimax-m3` is not advertised by the gateway's
  `/v1/models` and our key cannot reach it, yet the gateway routed to it. That is an `ai-gateway`
  configuration fix (fallback chain or key scope) and remains unresolved by design.
- **Retry behaviour on a non-retryable 403** was proposed and deliberately not implemented. The
  user scoped the change to the JSON parser and the markdown fence stripper only.
- **A failed job was observed to alternate between two errors across retries** (`Invalid \escape`,
  then `Invalid \escape`, then the 403) because `_call_with_retry` re-sends an identical body and
  the gateway re-rolls its routing each time. Not addressed.

## Relates to

- `.ai/decisions/llm/2026-10-31--bot-as-scoped-gateway-consumer-with-contract.md` — this is the
  same boundary from the routing side. The gateway is a first-class consumer relationship with a
  scoped virtual key and a TypeScript contract; this decision fixes which side of that contract
  decides the model.
- `.ai/decisions/llm/2026-10-31--litellm-escalate-interpretation.md` — confirms `LITELLM ESCALATE`
  is the Telegram chat code path and `LITELLM COMPACT` is a compaction label. Neither is an
  urgency flag or a plan-first override.
