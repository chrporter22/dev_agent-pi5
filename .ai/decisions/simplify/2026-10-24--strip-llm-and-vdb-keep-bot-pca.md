# Strip LLM and VDB services, keep bot + PCA

- **Date:** 2026-10-24
- **Decided by:** user (chat, this session)
- **Topic:** simplify

## Decision

Remove `core/vdb` (vector database / RAG / FAISS / SQLite embeddings) and `core/llm` (LiteLLM proxy) from the stack. The external ai-gateway (`~/ai-gateway`) provides all LLM capability and does its own RAG. The telegram bot in `core/bot` queues jobs to Redis; the worker reads from Redis, calls the ai-gateway directly over HTTP, and sends results back to Telegram. The PCA/ML monitoring stack (`core/ml`, `core/node-api`, `core/pca-backend`) remains unchanged.

## Why

- The vdb/llm services add complexity and container weight that duplicate what the external ai-gateway already provides
- User wants a lightweight bot interface for sending task requests when away from laptop
- PCA dashboard is still valuable for system health visibility
- Zero-trust posture preserved — bot and worker stay on internal_net; worker has outbound_net to reach ai-gateway

## What stays

- `core/bot` (telegram polling + command parsing)
- `core/ml` (background PCA/analytics loop)
- `core/node-api` (read-only ML Redis layer)
- `core/pca-backend` (React dashboard served by nginx)
- Redis (job queue only, no cache/source-of-truth role)

## What goes

- `core/vdb/` — entire directory deleted
- `core/llm/` — entire directory deleted
- `openclaw_llm_model` Docker volume (unused even before this change)
- `openclaw_vdb_data` Docker volume
- `LLM_ENDPOINT` env var (no longer needed)
- `llm_client.py` module (no longer needed)

## Supersedes / relates to

- Removes the last vestiges of the local-model era (`core/llm` proxying to LiteLLM was introduced 2026-10-19 in decision `llm/2026-10-19--replace-local-qwen-with-litellm.md`)
- Removes all RAG infrastructure (`core/vdb` was the highest-complexity service)