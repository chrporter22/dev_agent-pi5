# Vertical contract and key plan

- **Date:** 2026-10-31 21:09
- **Developer:** opencode (company-coder)
- **Topic:** llm

## Request

User asked for the leave-off point and a plan to connect `core/bot` to the external `~/ai-gateway`:
determine whether this repo's vertical endpoint is ready to connect, define a TypeScript contract
that accepts this repo as a consumer of the ai-gateway vertical, have ai-gateway issue the LiteLLM
key (and salt key) to be added to this repo, plan the endpoint connection contract plus remaining
steps, and update PRD and README once the plan is out.

## What was done

Investigation only — **no code, config, contract, or doc files were changed**. Verified the live
gateway and this repo's bot end-to-end, then produced a plan with three decisions surfaced to the
user for approval.

### Gateway-side verification (live, `~/ai-gateway` running)

- Orchestrator `:4001` is the real ingress: serves `/v1/chat/completions`, `/v1/models`, `/health`,
  forwards `Authorization` to LiteLLM, and reads `x-session-id` into `decision_records.session_id`
  (verified: a request carrying `x-session-id` landed a `decision_records` row with that exact
  session id, `application_id: coding`).
- `:4001` `/v1/models` exposes exactly one public model: `company-coder`. LiteLLM `:4000` exposes
  the full internal list (`coder-daily`, `coder-uiux`, `coder-complex`, `coder-planning`, backup
  models, `company-coder`, `router-classifier`).
- `response_format: {type: "json_object"}` survives the orchestrator (`ChatCompletionRequestSchema`
  is `.passthrough()`) and returns valid JSON for all three bot response shapes.
- A virtual key scoped to `models: ["company-coder"]` with a budget works through `:4001`
  (HTTP 200) and correctly rejects any other model (HTTP 403 `key_model_access_denied`).
- `scripts/create-dev-key.sh` is **broken**: it mints keys with `models: ["company/coder"]` (slash)
  while the served model name is `company-coder` (hyphen). A key minted that way 403s on every
  request. Gateway-side fix, separate repo.
- Truncation is real: without an explicit `max_tokens` the tier cap is 2048 tokens, and
  plan-shaped requests came back `finish_reason: length`, `completion_tokens: 2048`,
  `reasoning_tokens: 2048`, with content null or cut mid-string. Passing `max_tokens: 8000` in the
  request body produced a complete, parseable response.
- Latency through the gateway: plan-shaped calls measured 9.3s / 16.7s / 19.1s / 31.4s. A very long
  request exceeded the orchestrator's 120s upstream timeout and surfaced as HTTP 502
  "upstream gateway unreachable: timeout".
- The gateway's own `opencode/opencode.json` points at `:4000` (LiteLLM direct). The live opencode
  config on this host points at `:4001`. The `:4000` reference is stale relative to the gateway
  README/PRD boundary rule.

### This repo's readiness (all findings confirmed in Docker)

- **Hard blocker:** `core/bot/ai_gateway_client.py:140` annotates `model: Optional[str] = None` but
  line 4 imports only `Any, Callable, Dict, List` from `typing`. Importing the module raises
  `NameError: name 'Optional' is not defined`, confirmed by building the image and running the
  import. `core/bot/queue_worker.py:9` imports this module, so the worker container crash-loops on
  startup today. `core/bot/bot.py` does not import it, so the polling bot still starts.
- Model name mismatch: `core/bot/config.py:14` defaults `AI_GATEWAY_MODEL` to `gpt-4o-mini` and
  `.env.example:48` ships the same. The gateway does not serve that name (HTTP 400 "Invalid model
  name"). The correct public name is `company-coder`.
- `core/bot/ai_gateway_client.py:19` sets `TIMEOUT = 30`, below the measured 31.4s plan latency and
  far below the gateway's own 120s upstream timeout, so the client can abort a healthy call and
  burn all three retries.
- The client never sends `max_tokens`, so the gateway's 2048-token tier cap truncates plan output
  into invalid JSON and `_safe_parse_json` then raises — the exact failure the plan must prevent.
- `_safe_parse_json` assumes a string; a `content: null` response raises `AttributeError` inside
  the retry loop instead of a clear error.
- `core/bot/bot.py:394-403` — `/model <name>` stores any string, which 403s against a key scoped to
  `company-coder`.
- `docker-compose.prod.yml` gives `openclaw-bot` / `openclaw-worker` no `extra_hosts`, and on this
  Linux host (Docker 28.5.2) `host.docker.internal` does not resolve from a container. Verified
  from a container: `host.docker.internal` unresolvable by default, resolvable with
  `--add-host host.docker.internal:host-gateway`; `172.17.0.1` and the host LAN address both reach
  `:4001`.
- `.env` does not exist in this repo; `.env.example` ships a placeholder gateway URL pointing at a
  non-existent host.
- `INTEGRATION.md` (untracked) documents the wrong port (`:4000`), the wrong credential (master key
  pasted into this repo), and a model name the gateway does not serve.
- `core/bot/healthcheck.py` TCP-checks `AI_GATEWAY_BASE_URL` host/port — compatible with the
  planned URL once hostname resolution is fixed.

### Plan produced

Ordered subtasks: fix the `Optional` import; set the model name and base URL; add
`extra_hosts: ["host.docker.internal:host-gateway"]` to both bot services; raise the client timeout
and send explicit `max_tokens`; guard the JSON parser against null content; constrain `/model`;
mirror the contract; rewrite PRD / README / INTEGRATION against the verified state. Gateway-side
work (canonical contract file, changelog entry, `create-dev-key.sh` fix) stays in `~/ai-gateway`.

## Notable findings

- The gateway's key model distinguishes three secrets. `LITELLM_MASTER_KEY` and `LITELLM_SALT_KEY`
  are server-side only — the salt key encrypts stored virtual keys and the provider credential, so
  it must never leave the gateway. A client needs a **virtual key**, which is scoped per model and
  budget. The bot's credential should therefore be a virtual key scoped to `company-coder`.
- The previous plan (`.ai/decisions/llm/2026-10-31--lightweight-vertical-to-ai-gateway.md`)
  recorded "no OpenAPI spec / no contract artifact" and pointed the bot at `:4000` with the master
  key. The user's current request reverses both: a TypeScript contract is wanted, and the bot is
  to connect as a first-class consumer. That reversal needs its own decision file.
- The gateway PRD's boundary rule ("application adapters → orchestrator → LiteLLM → providers")
  makes `:4001` the correct target; `:4000` bypasses decision logging, routing, and spend
  attribution. This repo's `AGENTS.md` deviation "No `contract/` folder" was scoped to the internal
  node-api ↔ pca-backend split, so a contract mirror for the external gateway boundary needs an
  explicit note.
- The gateway hardcodes `application_id: "coding"`, so bot traffic is indistinguishable from
  OpenCode traffic in the decision log. Acceptable while both are coding workloads; changing it is
  gateway-side work.
- `parse_instruction` in the bot is currently dead code (nothing calls it). Left alone.
- The gateway's tier routing has explicit rules for the labels `LITELLM COMPACT` and
  `LITELLM EXECUTE`, but not for `LITELLM ESCALATE`; that label matched the generic "escalate"
  keyword and routed to the `complex` tier with `company-coder`.

## Open threads

- Three decisions await user confirmation before any file is changed: ingress port (`:4001`
  recommended), credential type (virtual key scoped to `company-coder`, never the salt key), and
  canonical contract location (`~/ai-gateway/contract/endpoints/` with a changelog entry, mirrored
  byte-identically into a new `contract/` folder here, which also needs an `AGENTS.md` deviation
  update).
- No implementation started. `core/bot/ai_gateway_client.py` still has the `Optional` import
  blocker, so the worker container cannot start.
- `.env` still needs to be created in this repo once the credential decision is made.
- Gateway-side follow-ups live in `~/ai-gateway`: fix the model name in
  `scripts/create-dev-key.sh`, add the new contract file and changelog entry, and decide whether
  bot traffic needs a distinct `application_id`.
- PRD, README, and INTEGRATION are all still describing the pre-integration state.
