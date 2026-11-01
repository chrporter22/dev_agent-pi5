---
name: security-rbac-zero-trust
description: Design and review code under RBAC + zero-trust, with per-service Redis ACLs as the datastore row-level-security equivalent and zero secrets in the frontend bundle. Use whenever adding or modifying auth, permissions, roles, API endpoints that touch user data, multi-tenant queries, env/secret handling, or any code that decides who can do what. Triggers: "add a role", "who can access this", "tenant isolation", "this endpoint returns user data", "store an API key", "set up Redis ACLs", "is this behind auth", writing route handlers, writing Redis ACL rules, adding a new permission, reviewing a PR for access control.
---

# Security: RBAC, Zero Trust, No Frontend Keys, Redis ACLs

The whole stack assumes the network is hostile, the client is untrusted, and the data store user is not "ours". Every layer enforces access on its own; if one layer fails, the next still denies.

Four rules, no exceptions:

1. **RBAC** — every action is permitted by an explicit role check. Default deny.
2. **Zero trust** — every request re-authenticates and re-authorizes. No implicit trust from prior requests, network location, or "logged in earlier".
3. **No keys in the frontend** — secrets, service tokens, master encryption keys, DB passwords, third-party API keys, and signing keys never appear in frontend code, frontend env, frontend bundles, or anything shipped to a browser.
4. **Least privilege at the datastore** — every service connects to Redis as its own user, scoped by key pattern *and* command set. The equivalent of database row-level security, enforced by Redis ACLs.

## RBAC

This repo has no multi-tenant SaaS layer and no Firebase. The auth boundary is a **single-operator gate**: the Telegram bot accepts commands only from the numeric user id in `ALLOWED_USER`, and every command passes through that check before any business logic runs.

- The gate lives at the top of the command dispatch path in `core/bot/bot.py`. Any new command must sit behind it — a new dispatch branch that reads user input before the gate is a bug.
- Default deny: a message that does not match a known command is not executed. It falls through to the help menu.
- Rate limiting is a second, independent gate: `core/bot/rate_limiter.py` caps commands per user so a compromised session cannot flood the queue or the external gateway.
- Audit every authorization failure: log the rejected user id, the command text, and the reason. Never log the token, the API key, or the secret values.

If a real role system is ever added, roles are coarse (`admin`, `editor`, `viewer`, plus project-specific roles). Permissions are fine-grained and assigned to roles, not users directly. Never check a user's id; check the role's permissions.

- One source of truth: a `permissions` matrix keyed by `<resource>:<action>` (`users:read`, `users:invite`, `billing:update`, `report:export`, ...). A role is a set of these.
- Enforce at the boundary — in route handlers and orchestrators — **before** any business logic reads or writes.
- Default deny: a permission that is not explicitly granted is denied. New endpoints require a decision on the matrix; do not assume "open by default".
- Role changes take effect on the next request; do not bake role info into JWTs longer than their short expiry, and always re-check against the source of truth on sensitive operations.
- Never use role hierarchy in code (e.g. `if (user.role === 'admin')`). Check a specific permission (`can(user, 'users:invite')`).

## Zero trust

The client proves who it is **on every request**. The server re-validates and re-decides. No "logged in" state is assumed from a previous hop.

- Authenticate every request: the Telegram bot token is the only credential the bot accepts, and `ALLOWED_USER` is re-checked per message. The Node API carries no end-user identity — it is an internal read-only projection of ML state, protected by network isolation plus Redis ACLs rather than by end-user auth.
- Authorize every request against the current role and current tenant — even for cached responses.
- Pin and validate the tenant per request (the repo's `x-org-id` header for multi-tenant projects) on the server side. Do not trust the client's chosen tenant. *Not applicable in this repo — there is no tenant layer. Say so rather than inventing one.*
- Validate input at the boundary with hand-written validators (this repo has no zod and no pydantic — validation is hand-written per service, per `AGENTS.md`). The schema is the contract; nothing past it runs untrusted values.
- Network segmentation is out of scope for the app, but in code: assume any service can be compromised, and add per-call auth between services (service tokens, mTLS) rather than trusting an internal network.
- Do not echo secrets, tokens, internal hostnames, or stack details in error responses. Use stable, generic error codes (`UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`) and log the detail server-side.
- **Path containment on any write that comes from outside the container.** The worker applies model-produced file changes into its sandbox: every target path must be normalized, rejected if absolute or if it escapes the sandbox root, and re-checked against the resolved absolute path. Two layers, because the input is machine-generated and the blast radius is the git working tree.

## No keys in the frontend

The frontend bundle is world-readable. Anything shipped there is effectively public. Treat the frontend as incapable of holding a secret.

The only frontend in this repo is the `pca-backend` React dashboard, served by nginx on the public port. It holds **zero** third-party credentials: it talks to the Node API over the compose network and reads from the browser's own copy of the response.

What never lives in the frontend:

- Third-party API keys (Stripe, SendGrid, OpenAI, Maps, ...).
- Service-to-service tokens or shared secrets for backend-to-backend auth.
- Master encryption keys or any key material used for AES-GCM at rest.
- DB connection strings, internal service URLs, internal hostnames, OAuth client secrets.
- Redis credentials — the dashboard never talks to Redis directly; `node-api` is the only reader.

What the frontend does hold:

- Its public config (build-time values only).
- No long-lived bearer tokens of any kind.

When the frontend needs to do something privileged (a Stripe refund, a SendGrid send, a DB write), it calls the backend. The backend holds the secret and authenticates the caller. Never proxy a key from the frontend and never embed one "because it's only the dev key".

Build-artifact check: grep the built `dist/` for secret-shaped strings before shipping a frontend change.

## Redis ACLs (the datastore row-level-security equivalent)

This repo has no SQL database. Redis is the datastore, so **Redis 7 ACLs are the row-level security mechanism**: one user per service, scoped by both key pattern and command set. `default` is `off` — a client that connects without a username gets nothing.

The live files:

- `redis/redis.conf` — the server config. `aclfile` points at the generated ACL; dangerous commands (`FLUSHDB`, `FLUSHALL`, `KEYS`, `CONFIG`, `SHUTDOWN`, `DEBUG`) are renamed to empty, so they fail at the protocol level.
- `redis/users.acl.template` — the source ACL with `${REDIS_PASSWORD_*}` placeholders.
- `redis/entrypoint.sh` — substitutes the placeholders from container env at boot and writes the real ACL to a tmpfs. It also strips `#` comment lines and blank lines: Redis 7 rejects comments in an ACL file and refuses to start on one.

Rules:

- **One user per service.** `bot`, `worker`, `ml`, `nodeapi`. Never share one user between two services: sharing a user means sharing its key patterns, which is how a read-only service ends up able to write.
- **Key patterns follow the data flow.** A service may only touch the keys it produces or consumes. `ml` writes `pca:*`, `drift:*`, `risk:*`, `model:*`, `ml:*`. `nodeapi` reads `pca:*`, `drift:*`, `risk:*`, `model:*`, `ml:heartbeat`, `ml:last_run`. `bot` and `worker` share the `chat:*`, `queue:*`, `job:*`, `jobs:*`, `rate:*`, `worker:*` space because they are one logical pipeline (the bot enqueues, the worker drains).
- **Read-only services are read-only by command set, not by key pattern alone.** `nodeapi` gets `-@all +get +lrange +ping` — exactly the commands `core/node-api` calls. A key-pattern-only ACL still lets a compromised reader run `SET` on a key it is allowed to read.
- **Rule order is load-bearing.** Redis applies ACL rules in order, so the blanket `-@all` must come **before** the `+cmd` grants. A trailing `-@all` cancels every earlier grant and the user can do nothing.
- **An ACL change is not done until it is exercised against a live Redis.** Compare the code's literal key names and Redis calls against the template, then run each service's own commands with that service's own credentials — including one operation the service must be denied. Reading the template does not prove the boundary holds.
- **ACL changes require a Redis restart.** The ACL file is read at startup; an in-place template edit changes nothing until the container is recreated.
- **Every service passes its own `REDIS_USER` and password.** The clients authenticate with `username=` explicitly — `core/bot/bot.py`, `core/bot/queue_worker.py`, `core/bot/chat_store.py`, `core/ml/redis_store.py`, and `core/node-api/src/redis/client.ts`.
- **Passwords come from env only.** They are never written into the template, the compose file, or any `.ai/` memory file. The template holds `${REDIS_PASSWORD_*}` placeholders; `entrypoint.sh` substitutes them at boot.
- **The substituted ACL does not persist.** It lives on a tmpfs inside the redis container, so a restart regenerates it from env rather than reading a stale file with old passwords.
- **Adding a service means adding an ACL user.** A new container that talks to Redis without its own user gets `default` — which is `off` — and fails closed. That is the intended behavior; add the user and its key patterns deliberately.
- **Renamed dangerous commands are a second layer, not the first.** Renaming `FLUSHALL` protects the instance from a confused client; the ACL is what actually scopes a service.

If a SQL service is ever added to this repo, it must ship with Postgres Row-Level Security enabled and forced in its first migration (`ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;` plus `ALTER TABLE <t> FORCE ROW LEVEL SECURITY;`), a tenant key set per request, one policy per access pattern with no permissive default, and a non-superuser request role with `BYPASSRLS` off. Do not add the service without the policies.

## Review checklist

When reviewing a change for security posture, walk this list:

- **RBAC:** new bot command passes the `ALLOWED_USER` gate and the rate limiter before doing work; new endpoint declares the permission it requires; the check runs before any read/write; failure is logged.
- **Zero trust:** input passes hand-written validation before use; a path that comes from the gateway is normalized and proven to stay inside the sandbox; error responses carry stable codes, not stack detail.
- **No frontend keys:** no secret-looking string in `core/pca-backend/src/**` or any code that builds the bundle. Frontend env files contain only public values. Grep the built `dist/`.
- **Redis ACLs:** a service that gained Redis access has its own ACL user with the narrowest key patterns and command set that works; `nodeapi` stays read-only; `default` stays `off`; no password literal in the template, the compose file, or `.ai/`. The template was diffed against the code's actual key names and every service's ACL was exercised against a live Redis, including a denied operation.
- **Container posture:** `read_only: true` retained, `cap_drop: ALL` retained, `no-new-privileges` retained, tmpfs mounts limited to the writable surfaces the service actually needs.
- **Logging:** auth failures and permission denials are logged; no tokens, passwords, or gateway keys are logged.
- **Secrets:** any secret read from env is consumed server-side only; rotation is documented; raw values are never written to `.ai/` (see `pii-redaction`).

## Anti-patterns to refuse

- "Trust the frontend to send the user id" — always read it from the verified token.
- "It's an internal service, no auth needed" — internal services authenticate too.
- "We'll add the ACL user later" — add it now, before the service reads anything. `default off` means it fails closed, which is correct.
- "Just give node-api write access too, it might need it" — widen the ACL when the need is real, not speculatively.
- "Hard-code the role for testing, we'll fix it" — gate the test with a permission like everything else.
- "Just put the key in `VITE_*` so it gets baked in" — no. Frontend env is public.
- "Hide the secret in the bundle" — anything in the bundle is not a secret.

## Scope

Applies to every code change that touches auth, permissions, data access, secrets handling, or the request path. Sits on top of the engineering standards in `AGENTS.md` (structured logging, soft delete, multi-tenant keys) and the `pii-redaction` and `docker-testing` skills.
