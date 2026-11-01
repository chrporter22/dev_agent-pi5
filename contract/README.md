# Contract

This directory is a **mirror** of the canonical contract owned by the external gateway repo
(`~/ai-gateway/contract/`).

The gateway owns the wire format, so it holds the canonical copy and the live changelog. This
folder holds a byte-identical copy of the files this repo implements against, hand-copied at each
contract change. The gateway's `contract/CHANGELOG.md` is the single ledger for both sides —
entries move from `needs-implementation` to `done` there, not here.

| File | Canonical source | What this repo does with it |
|---|---|---|
| `endpoints/dev-agent-bot.contract.ts` | `~/ai-gateway/contract/endpoints/dev-agent-bot.contract.ts` | `core/bot/ai_gateway_client.py` implements the request/response surface it describes. |

## Why the bot does not import this file

`core/bot` is Python and this repo has no zod, so the TypeScript schema is a typed specification
rather than a runtime dependency. The Python client mirrors the schema's constraints by hand:
model allow-list, token ceiling, finish-reason handling, and the error shape. When the schema
changes, the hand-written client changes with it.

## Cutover procedure

1. The gateway side edits the canonical file and appends a `needs-implementation` entry to
   `~/ai-gateway/contract/CHANGELOG.md`.
2. This repo's agent hand-copies the changed file into this folder, implements the change in
   `core/bot`, and flips the changelog entry to `done` on the gateway side.

## Related

- Decision: `.ai/decisions/llm/2026-10-31--bot-as-scoped-gateway-consumer-with-contract.md`
- Handoff runbook: `INTEGRATION.md`
