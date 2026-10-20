# Replace local Qwen2-1.5B with external LiteLLM gateway

- **Date:** 2026-10-19
- **Decided by:** user (chat, this session)
- **Topic:** llm

## Decision

Replace the local Qwen2-1.5B-Instruct model (llama.cpp, served by `openclaw-llm`) with an external LiteLLM gateway. `openclaw-llm` is repurposed from "local inference engine" into a thin Flask proxy that preserves the existing `POST /parse` strict-JSON contract for `core/bot`. The external LiteLLM gateway lives in a separate user-owned repo (`~/ai-gateway`); this repo only adds placeholders for its base URL and API key and never touches the gateway itself.

## Why

- The local Qwen2-1.5B model is not powerful enough for the planned workload.
- A LiteLLM proxy is already running in another repo and provides stronger capability behind an OpenAI-compatible `/v1/chat/completions` endpoint.
- Keeping `core/llm` as a thin proxy preserves the existing `core/bot` consumer code unchanged — minimal blast radius.
- Routing the call through `core/llm` (not `core/bot` directly) keeps `core/bot` on `internal_net` only and confines the new egress surface to one container.

## Trade-offs considered

- **Replace entirely vs augment (gateway as fallback):** user chose replace; `core/llm` no longer ships a model.
- **Direct call from `core/bot` vs proxy in `core/llm`:** user chose proxy; preserves `core/bot` zero-trust posture.
- **Local model kept as dormant service vs fully removed:** user chose repurpose; service stays in compose with a new identity.

## What stays

- `core/bot` consumer code (`llm_client.py`, `queue_worker.py`, `config.py`) is unchanged. It still calls `LLM_ENDPOINT` over `internal_net`.
- The `POST /parse` request/response shape is unchanged.
- Zero-trust primitives on `openclaw-llm`: `read_only: true`, `cap_drop: ALL`, `no-new-privileges`, `pids_limit`, tmpfs.
- The `openclaw_llm_model` named volume remains declared (back-compat with any external docs/scripts), just no longer mounted.

## What changes

- `openclaw-llm` becomes a stateless Flask proxy, ~256MB RAM instead of 8GB, slim Python base image.
- `openclaw-llm` gains `outbound_net` and DNS (necessary to reach the gateway); all other services stay on `internal_net`.
- New env vars: `AI_GATEWAY_BASE_URL`, `AI_GATEWAY_API_KEY`, `AI_GATEWAY_MODEL` — required, validated at startup.
- The `core/llm/llm-server/` directory (containing `start-llm.sh`) is removed. Side effect: clears the AGENTS.md known-broken port-8081-vs-8080 mismatch.
- AGENTS.md and root README descriptions of the LLM stack are updated.

## Deferred to user

- Setting real `AI_GATEWAY_BASE_URL` and `AI_GATEWAY_API_KEY` values in `.env`. Service refuses to start without them, by design.
- Any tuning of upstream model choice or temperature in `core/llm/app.py` `SYSTEM_PROMPT`.

## Supersedes / relates to

- Replaces the prior implicit decision ("local llama.cpp is the inference path") reflected in AGENTS.md line 138, `core/llm/README.md`, and root `README.md` lines 113/129 — those documents are updated as part of this same change.
