# Bot connects to ai-gateway as a scoped consumer with a TypeScript contract

- **Date:** 2026-10-31
- **Decided by:** user (chat, this session)
- **Topic:** llm

## Decision

The Telegram bot in `dev_agent-pi5` connects to the external `~/ai-gateway` as a first-class
consumer, not a loose client. Three specifics are confirmed:

1. **Ingress is the orchestrator on port 4001**, not LiteLLM on 4000. Bot traffic is an
   application adapter talking to the orchestrator, which then handles routing, decision logging,
   and spend attribution before reaching the model providers.
2. **The bot authenticates with a per-consumer virtual key**, scoped to the models it is allowed
   to call and carrying a spend budget. The gateway's master key and salt key stay inside the
   gateway. The salt key is never copied into this repo under any circumstance.
3. **The interface between the two repos is a TypeScript contract.** The canonical copy lives in
   the gateway repo, where the server side owns the wire format. This repo keeps a byte-identical
   mirror so the consumer side has a typed reference to implement against.

## Why

The gateway's own PRD draws the boundary as application adapters → orchestrator → LiteLLM → model
providers. A bot calling LiteLLM directly would bypass decision logging, routing, shadow scoring,
and spend attribution, making the bot's traffic invisible to the gateway's own observability. The
orchestrator is the single ingress the gateway is designed around, and it is the same ingress the
live OpenCode client already uses.

A master key in this repo would grant key generation, spend-log access, and budget administration
to a Telegram bot. A virtual key scoped to a single model and bounded by a budget is revocable,
minimal, and sufficient for what the bot actually does. The salt key encrypts stored virtual keys
and the provider credential inside the gateway; a copy outside the gateway has no legitimate use
and would widen the blast radius of any leak.

The prior plan recorded "no OpenAPI spec, no contract artifact" and treated the bot's client file
as the whole contract. That was written before the bot was verified against a live gateway, and it
did not survive contact with the gateway's real behaviour: the model name served, the token cap
the gateway applies to plan-shaped requests, the orchestration timeout, and the model-scoped
authorisation model all need to be written down somewhere that both repos can point at. A shared
contract file is the cheapest way to keep the two sides honest.

## Supersedes / relates to

- `.ai/decisions/llm/2026-10-31--lightweight-vertical-to-ai-gateway.md` — the prior decision. It
  specified no contract artifact, pointed the bot at LiteLLM directly, and assumed the bot would
  paste the master key into this repo. This decision replaces the contract-artifact and
  credential parts of it, and changes the target from LiteLLM to the orchestrator. The rest of that
  decision stands: one endpoint, bearer auth, three system-prompt patterns, no facade route.
- `.ai/decisions/llm/2026-10-31--litellm-escalate-interpretation.md` — confirms the gateway tech
  is LiteLLM and that the `LITELLM ESCALATE` label is the Telegram chat code path.
- `.ai/decisions/security/2026-10-28--no-api-keys-in-frontend-rls-in-database.md` — the security
  baseline this decision is an instance of. The bot is a backend service, so a credential in its
  environment is consistent with that baseline; the point of the virtual key is that it carries
  the minimum authority needed and nothing more.
