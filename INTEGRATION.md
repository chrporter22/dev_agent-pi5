# INTEGRATION — bot ↔ gateway handoff

> **Current state: the connection is configured and verified.** This file is the runbook for
> re-establishing or re-verifying it, and for understanding what changed from the earlier
> "switch to `~/ai-gateway`" handoff. It no longer contains stale instructions.

## What the bot expects from the gateway

One endpoint: **`POST /v1/chat/completions`**, OpenAI-compatible, bearer auth. Three
system-prompt patterns over that endpoint — no facade route, no custom schema.

| Call | `response_format` | `max_tokens` | Shape |
|---|---|---|---|
| `parse_instruction` | `json_object` | 8000 | `{type, language, features, description}` |
| `chat` | none | 8000 | prose |
| `plan_changes` | `json_object` | 8000 | `{files: [{path, action, content}]}` |

Contract: `contract/endpoints/dev-agent-bot.contract.ts` (byte-identical mirror of the canonical
copy in `~/ai-gateway/contract/`). Decision: `.ai/decisions/llm/2026-10-31--bot-as-scoped-gateway-consumer-with-contract.md`.

## The three things that changed

### 1. Target the orchestrator on `:4001`, not LiteLLM on `:4000`

The gateway exposes two HTTP surfaces:

- **`:4001` — orchestrator.** The single ingress. Scores the request, picks a route, records the
  decision, tracks spend, then forwards to LiteLLM.
- **`:4000` — LiteLLM.** The raw proxy in front of the model providers.

Calling `:4000` works, but it bypasses every layer the gateway exists to provide: the request
never appears in the decision log, no tier routing happens, no shadow scoring compares the
recommended route against the live one, and the spend is not attributed. The bot's traffic
becomes invisible.

`AI_GATEWAY_BASE_URL=http://host.docker.internal:4001`

### 2. Authenticate with a scoped virtual key, not the master key

The gateway has three secrets. Only one of them belongs in this repo.

| Secret | Where it lives | Why |
|---|---|---|
| `LITELLM_MASTER_KEY` | `~/ai-gateway/.env` only | Admin authority: can mint keys, read spend logs, change budgets. |
| `LITELLM_SALT_KEY` | `~/ai-gateway/.env` only | Encrypts stored virtual keys and the provider credential inside the gateway. A copy here has no legitimate use and would turn any leak in this repo into a credential-database compromise. |
| **Virtual key** | this repo's `AI_GATEWAY_API_KEY` | Scoped to the models this consumer may call, bounded by a budget, revocable in one step. |

Mint one:

```bash
cd ~/ai-gateway
set -a && . ./.env && set +a
LITELLM_URL=http://localhost:4000 bash scripts/create-dev-key.sh dev-agent-pi5 20 openclaw-bot
```

The script prints the generated key. Paste it into this repo's `.env` as `AI_GATEWAY_API_KEY`.

The key is scoped to `company-coder` — the only model the orchestrator serves publicly. A request
for any other model returns HTTP 403 (`key_model_access_denied`).

> **Note on the script.** It previously requested `models: ["company/coder"]` (slash) while the
> gateway serves `company-coder` (hyphen). Every key it minted was rejected on every request,
> and the failure looked like an authorisation problem rather than a naming mistake. Fixed
> 2026-10-31.

### 3. Send `max_tokens`, and raise the timeout

Two gateway behaviours that the earlier client got wrong:

- **Token cap.** The routing tier caps responses at 2048 tokens. Structured plan output longer
  than that comes back with `finish_reason: "length"` and content truncated mid-string — which
  the client then fails to parse as JSON, and which the retry loop cannot fix. Sending an
  explicit `max_tokens` overrides the tier cap. Verified: with `max_tokens: 8000` a plan request
  returns 2074 completion tokens and parses cleanly.
- **Latency.** Measured plan-shaped calls through the gateway took 9.3s, 16.7s, 19.1s, and
  31.4s. The client's old 30-second timeout aborted healthy calls and then burned all three
  retries on them. The gateway's own upstream timeout is 120 seconds. `AI_GATEWAY_TIMEOUT=150`
  keeps the client above it, so a genuine upstream failure surfaces as the gateway's own 502
  rather than as a client-side timeout.

## Container networking

On Linux, Docker does not add `host.docker.internal` automatically — that is a Docker Desktop
convenience. Both `openclaw-bot` and `openclaw-worker` therefore carry:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

Without it, name resolution fails and the worker logs a connection error. If the mapping is ever
removed, the alternatives are the Docker bridge gateway (`172.17.0.1`) or the host's LAN IP.

## Verification

```bash
# 1. The gateway is up and serving the model this repo expects
curl -sS http://localhost:4001/v1/models -H "Authorization: Bearer $AI_GATEWAY_API_KEY"
#    -> {"object":"list","data":[{"id":"company-coder",...}]}

# 2. A chat call works from inside the worker container
docker exec openclaw-worker python -c "
from ai_gateway_client import chat
print(chat([{'role':'user','content':'reply pong'}]))
"
#    -> pong

# 3. A plan call returns parseable JSON
docker exec openclaw-worker python -c "
import json
from ai_gateway_client import plan_changes
print(json.dumps(plan_changes('add a health endpoint', {'files': ['app.py'], 'language': 'python'}))[:200])
"

# 4. The decision landed in the gateway's decision log, correlated by session id
docker exec ai-gateway-postgres-1 psql -U litellm -d litellm -c \
  "SELECT session_id, application_id, tier, status FROM decision_records ORDER BY created_at DESC LIMIT 5;"
```

`x-session-id` carries the job id, so a decision record can be traced back to the Telegram job
that caused it.

## What "done" looks like

- [x] `~/ai-gateway` running, orchestrator reachable on `:4001`
- [x] Scoped virtual key minted and stored in this repo's `.env`
- [x] `.env` carries the orchestrator URL, the key, and `company-coder`
- [x] `docker compose -f docker-compose.prod.yml up -d --build` succeeds
- [x] `docker exec openclaw-worker python -c "...chat..."` prints a reply
- [ ] `/chat hello` returns a reply in Telegram (needs `TELEGRAM_TOKEN` + `ALLOWED_USER`)
- [ ] `/build owner/repo add a README section` opens a PR (needs `GITHUB_TOKEN`)

The two unchecked items need secrets this repo does not have yet.

## Troubleshooting

| Failure | Check |
|---|---|
| `Connection refused` / DNS failure | `AI_GATEWAY_BASE_URL` and the `extra_hosts` mapping. From inside: `docker exec openclaw-worker python -c "import socket; socket.create_connection(('host.docker.internal', 4001), 5)"` |
| HTTP 401 | The key is not the one the gateway issued, or the gateway restarted and rotated its store. Re-mint. |
| HTTP 403 | The key is not scoped to the model being requested. Check the key's `models` list. |
| HTTP 400 "Invalid model name" | `AI_GATEWAY_MODEL` names a model the orchestrator does not serve. It serves `company-coder`. |
| JSON parse failure on a plan | The response was truncated. Raise `AI_GATEWAY_MAX_TOKENS`. |
| Request timeout | Raise `AI_GATEWAY_TIMEOUT` above the observed latency. |
| No response in Telegram | `TELEGRAM_TOKEN` wrong or `ALLOWED_USER` mismatch. `docker logs openclaw-bot` shows the polling error. |

## When you come back to `dev_agent-pi5`

- **The bot's client is the implementation of the contract, not the contract itself.** If the
  gateway's surface changes, change `contract/endpoints/dev-agent-bot.contract.ts` on the gateway
  side first, copy it here, then update `core/bot/ai_gateway_client.py`.
- **The bot retries 3× with backoff**, but only on 5xx, 429, and transport errors. A 4xx fails
  fast — retrying a 403 just burns time.
- **`/model` is constrained.** Only names in `AI_GATEWAY_ALLOWED_MODELS` are accepted.
- **Redis ACLs are per-service.** The bot user and worker user are the two that touch the bot's
  data. Don't add a fifth user without updating `redis/users.acl.template`.

## Cross-reference

- Decision (this repo): `.ai/decisions/llm/2026-10-31--bot-as-scoped-gateway-consumer-with-contract.md`
- Decision (gateway repo): `~/ai-gateway/.ai/decisions/consumers/2026-10-31--external-consumers-via-orchestrator-with-scoped-keys.md`
- Contract mirror: `contract/` (see `contract/README.md`)
- Session history: `.ai/sessions/llm/2026-10-31-2109--vertical-contract-and-key-plan.md`
- Why the gateway exists: `.ai/decisions/llm/2026-10-19--replace-local-qwen-with-litellm.md`
