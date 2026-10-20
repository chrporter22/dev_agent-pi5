# LLM Proxy Container (openclaw-llm)

Thin stateless proxy to an external LiteLLM gateway.  
Target deployment: containerized stack on a Raspberry Pi 5 (ARM64).  
Security model: zero trust, single egress point to the gateway.

---

## Purpose

`openclaw-llm` is a Flask service that forwards `POST /parse` requests from
`openclaw-bot` to a LiteLLM-compatible gateway running elsewhere and returns
strict JSON. It is the **only** service in this stack with outbound internet
access.

It does not run a model. It does not download weights. It does not persist
anything to disk.

Architectural flow:

```
Telegram
  → openclaw-bot
  → openclaw-llm (this container, over internal_net)
  → external LiteLLM gateway (over outbound_net)
  → openclaw-llm
  → openclaw-bot
  → GitHub Repo B
```

The LLM (whichever model the gateway serves) is subordinate to the bot and
never makes execution decisions.

---

## Upstream Gateway

The LiteLLM gateway is a separate user-owned repo (`~/ai-gateway`). It is
configured to expose an OpenAI-compatible `/v1/chat/completions` endpoint
and authenticate with a bearer token.

This repo does **not** include or manage the gateway. It only consumes it.

Required environment variables (set in `.env`, validated by `core/llm/config.py`):

| Variable               | Purpose                                       |
|------------------------|-----------------------------------------------|
| `AI_GATEWAY_BASE_URL`  | Base URL of the gateway (e.g. `https://...`)  |
| `AI_GATEWAY_API_KEY`   | Bearer token sent in `Authorization` header   |
| `AI_GATEWAY_MODEL`     | Model name to request on the gateway          |

Optional, with defaults:

| Variable                  | Default                  |
|---------------------------|--------------------------|
| `LLM_PORT`                | `8080`                   |
| `LLM_TIMEOUT_SECONDS`     | `30`                     |
| `LLM_MAX_RETRIES`         | `2`                      |
| `LLM_GATEWAY_CHAT_PATH`   | `/v1/chat/completions`   |

The service refuses to start if any required variable is missing or malformed.

---

## API Specification

Base URL (internal only, exposed on `internal_net`):

```
http://openclaw-llm:8080
```

The container does NOT expose ports to the host.

### `POST /parse`

Structured instruction parsing endpoint. Contract preserved verbatim for
`openclaw-bot`.

Request:

```json
{
  "instruction": "Create a CLI tool that reads CSV and runs PCA"
}
```

Response (200):

```json
{
  "type": "cli_tool",
  "language": "python",
  "features": ["pca", "csv"],
  "tests": true,
  "description": "CLI tool for PCA on CSV datasets"
}
```

Error responses:

| Status | When                                                       |
|--------|------------------------------------------------------------|
| `400`  | Missing/empty `instruction`                                |
| `502`  | Upstream gateway HTTP error or unparseable response         |
| `504`  | Upstream gateway timeout                                   |

The proxy requests the upstream with:

- `response_format: {"type": "json_object"}` (strict JSON mode)
- `temperature: 0.2`
- A fixed `system` prompt instructing the model to return only the schema above

Hand-written validation rejects:

- Empty `choices[0].message.content`
- Non-object JSON
- Anything other than what the existing `core/bot/llm_client.py` already
  validates downstream (language/feature shape, etc.)

### `GET /health`

Returns `{"status": "ok"}`. Cheap, no upstream call.

---

## Security Model

Zero trust enforcement.

The proxy container:

- Runs as non-root user `llmuser`
- Has read-only root filesystem
- Drops all Linux capabilities
- Uses `no-new-privileges`
- Has `pids_limit` enforced (100)
- Has memory limit enforced (512 MB)
- Has no docker.sock
- Has no privileged flags
- Has no host mounts
- Exposes no public ports
- Stores no secrets at rest (gateway key is only in env, never logged)

Network posture:

- Attached to `internal_net` (talks to `openclaw-bot`, `openclaw-worker`)
- Attached to `outbound_net` (talks to the external LiteLLM gateway)
- DNS is allowed (required to resolve the gateway hostname)
- Cannot reach Redis, Telegram, GitHub, or any other internal service

Egress is **single-purpose**: only the configured `AI_GATEWAY_BASE_URL` is
expected to be contacted. Add egress filtering at the host level (e.g. iptables
on the docker host) for defense in depth if the deployment environment supports
it.

---

## What Was Removed (vs. the Prior Local-Model Era)

This service no longer:

- Builds or runs `llama.cpp`
- Loads a GGUF model from disk
- Mounts the `openclaw_llm_model` Docker volume
- Holds an 8 GB memory footprint
- Uses `dns: []` (the gateway hostname must resolve)

The `core/llm/llm-server/` directory and its `start-llm.sh` have been removed
from this repo. Image size drops from multi-GB to ~150 MB.

---

## Resource Limits

| Resource | Value   |
|----------|---------|
| Memory   | 512 MB  |
| PIDs     | 100     |
| Swap     | none    |
| CPU      | unset (default) |

Peak usage across all containers should stay well under the host total.

---

## Deployment

Built and run via Docker Compose. Required env vars in `.env`:

```
AI_GATEWAY_BASE_URL=https://your-litellm-host.example.com
AI_GATEWAY_API_KEY=your_litellm_api_key_here
AI_GATEWAY_MODEL=gpt-4o-mini
```

Verification (from the host):

```bash
docker inspect openclaw-llm
```

Confirm:

- `ReadOnlyRootFilesystem: true`
- `CapDrop: ALL`
- `SecurityOpt`: `no-new-privileges:true`
- `Memory` ≤ 536 MB
- No `dns: []`
- No host bind mounts
- No exposed host ports
- `Networks`: `internal_net` + `outbound_net`

Functional smoke test:

```bash
docker compose exec openclaw-bot \
  python -c "import requests; print(requests.post('http://openclaw-llm:8080/parse', json={'instruction': 'ping'}).json())"
```

Or directly from the host network if reachable:

```bash
curl -s http://openclaw-llm:8080/health
```

---

## Acceptance Criteria

Deployment:

- Container launches successfully
- Refuses to start without `AI_GATEWAY_*` env vars
- Runs as non-root
- Root filesystem read-only
- Egress only to `AI_GATEWAY_BASE_URL`
- No public ports

Functional:

- `/health` returns `200 {"status": "ok"}`
- `/parse` returns valid JSON for a real instruction when the gateway is reachable
- `/parse` returns `502`/`504` cleanly when the gateway is not

Security:

- No shell execution exposed
- No arbitrary code execution
- No host filesystem access
- No GitHub / Telegram / Redis access
- No secret values in logs

---

## Architectural Role

Control plane:

```
Telegram
  → openclaw-bot
  → openclaw-llm (this proxy)
  → external LiteLLM gateway
  → openclaw-llm
  → openclaw-bot
  → GitHub Repo B
```

The proxy is never the decision-maker. It is a constrained subordinate
service used by `openclaw-bot`.
