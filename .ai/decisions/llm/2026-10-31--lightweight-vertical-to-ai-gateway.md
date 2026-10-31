# Lightweight vertical integration: bot ↔ ai-gateway

- **Date:** 2026-10-31
- **Decided by:** user (chat, this session)
- **Topic:** llm

## Decision

The bot (`core/bot`) talks to the external ai-gateway over a **standard OpenAI-compatible endpoint** (`POST /v1/chat/completions`) with bearer auth. The ai-gateway is treated as a plain LiteLLM proxy — no custom route, no gateway-side facade, no client-side OpenAPI spec on this repo. The three bot methods (`chat`, `parse_instruction`, `plan_changes`) are different system-prompt patterns over the **same** endpoint, not different endpoints.

## Why

- **LiteLLM already speaks OpenAI.** The gateway is `~/ai-gateway` running LiteLLM. It already exposes `POST /v1/chat/completions`, supports `Authorization: Bearer …`, and supports `response_format: {type: "json_object"}` via OpenAI-compat passthrough. Re-implementing any of this on the bot side or adding a gateway-side wrapper would be redundant work and a new layer to maintain.
- **One endpoint = one contract.** The three methods on the client differ only in the system prompt and (for `parse_instruction` / `plan_changes`) the `response_format` flag. The endpoint shape is identical. Splitting them into three routes on the gateway would just re-create the same shape three times.
- **No OpenAPI spec on this repo.** OpenAPI's value is when there are multiple consumers or when a non-trivial schema is hand-rolled. Here the consumer is a single Python file and the schema is OpenAI's (well-documented, well-tested). A bot-side `openapi.yaml` would be a duplicate of the OpenAI spec with two extra fields (`response_format: json_object`, our three system prompts) — both of which fit in 30 lines of a `ai_gateway_client.py` docstring.
- **The contract that matters is the JSON *response shape* the bot expects back from `plan_changes` and `parse_instruction`.** That lives in the bot code (`core/bot/ai_gateway_client.py` lines 29-62), not in a separate spec file. Anyone changing the contract edits the client and the system prompt together.

## What the ai-gateway repo needs

For the bot to work, the ai-gateway (LiteLLM) just needs to:

1. **Expose `POST /v1/chat/completions`** — LiteLLM default. No work.
2. **Accept `Authorization: Bearer <AI_GATEWAY_API_KEY>`** — LiteLLM default with `LITELLM_MASTER_KEY` set. No work.
3. **Support `response_format: {type: "json_object"}`** — LiteLLM passes this through to OpenAI-compatible providers (and the Ollama/OpenRouter/Anthropic backends it wraps). If the gateway uses a backend that doesn't support JSON-mode (some local models, some OSS routes), the bot will get a parse error and the gateway logs will show the `response_format` rejection. Fix: either switch the route to a JSON-mode-capable backend, or remove `response_format` from the bot's request and rely on the system prompt alone.
4. **Reachability from this stack.** The bot container is on `outbound_net` with DNS. The gateway URL must be reachable from the host running `docker compose`. If the gateway is on the same host (`http://host.docker.internal:4000`), set `AI_GATEWAY_BASE_URL=http://host.docker.internal:4000`. If it's on the LAN, set the LAN IP.
5. **A model name that works.** `AI_GATEWAY_MODEL` (default `gpt-4o-mini` in `.env.example`) must be a model the gateway has configured. If the gateway is gated behind a `LITELLM_MODEL_GROUP` allow-list, the bot's default has to be on the list. The user can override per-chat via the `/model` command.

That is the entire integration surface. No new routes, no new env vars on the gateway side, no new schema.

## What this repo ships (already done)

`core/bot/ai_gateway_client.py` (170 lines):

- `chat(messages, system=…, model=None) -> str` — free-text reply. Used by `/chat`.
- `parse_instruction(instruction) -> Dict` — `{type, language, features, description}`. Currently unused by command paths but kept for future `/plan` command. Safe to delete if it stays unused for one more release.
- `plan_changes(instruction, repo_context) -> Dict` — `{files: [{path, action, content}]}`. Used by `/build`.

All three call `_request_gateway()` (line 78) which POSTs to `${AI_GATEWAY_BASE_URL}/v1/chat/completions` with bearer auth and `Content-Type: application/json`. All three go through `_call_with_retry()` (line 104) which retries 3× with exponential backoff (0.5s base, ±0.25s jitter). On final failure the worker marks the job `failed` and sends the error string to Telegram — the bot never crashes on gateway outages.

`core/bot/config.py`:

- `AI_GATEWAY_BASE_URL` (required) — gateway base URL, no trailing slash.
- `AI_GATEWAY_API_KEY` (required) — bearer token.
- `AI_GATEWAY_MODEL` (default `gpt-4o-mini`) — used by `parse_instruction` and `plan_changes`. `chat()` reads the per-chat override (`chat:{chat_id}:model`) set by `/model`, falling back to this default.

`.env.example`:

```
AI_GATEWAY_BASE_URL=https://your-litellm-host.example.com
AI_GATEWAY_API_KEY=your_litellm_api_key_here
AI_GATEWAY_MODEL=gpt-4o-mini
```

## Trade-offs considered

- **OpenAI-compat (chosen) vs custom JSON-RPC.** OpenAI-compat wins because the bot code is 170 lines instead of ~400, the gateway is already running LiteLLM, and any future consumer (a CLI, a second bot, a notebook) can talk to the same gateway with no extra glue.
- **No facade route on the gateway (chosen) vs `/v1/dev-agent-bot/plan` wrapper.** A facade would let the gateway enforce the JSON shape server-side and return 400 on a malformed plan. But the bot already retries 3× and the malformed-plan failure mode is "user sees the error and retries" — a facade only buys centralized validation at the cost of one more route to keep in sync with the system prompt. Reject.
- **No OpenAPI spec on this repo (chosen) vs publishing one.** A spec would document the request/response shape for `parse_instruction` and `plan_changes`. But OpenAPI's strength is multi-consumer + hand-rolled schema. Here: one consumer (this repo), one endpoint (`/v1/chat/completions`), and the JSON shape lives in 8 lines of system prompt. Reject.
- **LiteLLM-only (chosen) vs gateway-agnostic.** If the user later swaps to a non-LiteLLM gateway, this contract still holds as long as the new gateway speaks OpenAI-compat. The bot does not import `litellm` and does not depend on any LiteLLM-specific feature.

## Deferred to user

- Confirming the gateway actually has `gpt-4o-mini` (or whatever model) configured and reachable.
- Setting real `AI_GATEWAY_BASE_URL` and `AI_GATEWAY_API_KEY` in `.env`. The worker refuses to process jobs until the gateway responds on the healthcheck (`core/bot/healthcheck.py` — TCP check on `AI_GATEWAY_BASE_URL`).
- If the gateway uses a model allow-list, ensuring the bot's default (`AI_GATEWAY_MODEL`) is on it.
- Per-chat model overrides via the `/model` command (stored at `chat:{chat_id}:model` in Redis) — purely a UX nicety; the default model still works.

## Supersedes / relates to

- Builds on `.ai/decisions/llm/2026-10-19--replace-local-qwen-with-litellm.md` (the original "use LiteLLM" decision) by recording what the integration contract *is*, not just *that it exists*.
- Relates to `.ai/decisions/llm/2026-10-31--litellm-escalate-interpretation.md` — the `LITELLM ESCALATE` / `LITELLM COMPACT` / `LITELLM EXECUTE` labels are project-internal names confirming LiteLLM is the gateway tech. They are not separate modes or routing rules; this decision is what they all run over.
- Closes Phase 5 item 5 from `.ai/sessions/llm/2026-10-28-2053--LEAVE-OFF.md` (the `lightweight-vertical-to-ai-gateway` decision file).

## How to verify

After wiring `.env`, in a shell with the stack running:

```bash
docker exec openclaw-worker python -c "
from ai_gateway_client import chat
print(chat([{'role': 'user', 'content': 'reply with the word pong'}]))
"
```

Expected: `pong`. If you get an `ai-gateway failed after 3 retries` trace, the gateway is unreachable or the model isn't configured — check `docker logs openclaw-worker` for the HTTP status code the gateway returned.
