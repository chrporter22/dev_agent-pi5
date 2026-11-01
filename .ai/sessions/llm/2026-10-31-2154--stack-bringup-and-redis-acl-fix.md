# Stack bring-up and redis ACL correction

- **Date:** 2026-10-31 21:54
- **Developer:** opencode (company-coder)
- **Topic:** llm

## Request

Continuation of the gateway-integration session. The requested work was to finish getting the stack
running and verify the gateway path end to end. The `LITELLM ESCALATE` marker in the prompt is an
upstream tier-routing hint, not a directive to the agent, and was ignored accordingly.

## What was done

Verified the full stack, then found and fixed four independent pre-existing defects that were
preventing it from running at all. None of these were visible while the plan was being written,
because the plan phase never brought the containers up.

### Gateway path verified live

- The bot image builds and the client module imports cleanly inside the container.
- A live `chat()` call through the gateway returned a valid reply.
- A live `plan_changes()` call returned parseable JSON with the expected `files` key.
- Container-side configuration confirmed: timeout 150s, max tokens 8000, model `company-coder`,
  allowed-model list containing only `company-coder`.

### Defect 1 — redis refused to start at all

The redis ACL template carried a documentation header written as `#` comment lines. Redis 7's ACL
parser does not accept comments in the ACL file and aborts startup on the first one. Verified
against both `redis:7-alpine` and `redis:7.2-alpine`; both reject comment lines identically.

Fixed in the redis entrypoint by stripping comment and blank lines while substituting the
passwords. The template keeps its header for humans; the generated ACL file is comment-free.

### Defect 2 — the nodeapi ACL denied every command it was supposed to allow

Redis ACL rules are applied in order. The nodeapi rule listed its command grants first and the
deny-all rule last, so the trailing deny wiped every earlier grant. The result was that the
dashboard's read-only API user could not read anything, and the redis healthcheck could not ping.

Confirmed against a scratch redis: grants-then-deny-all yields no permission, deny-all-then-grants
yields the intended permission. Fixed by moving the deny-all ahead of the grants.

This was the root cause of the dashboard returning 500s and 502s, not a node-api code bug.

### Defect 3 — ACL key patterns did not cover the keys the services actually use

Audited every redis key literal in `core/bot`, `core/ml`, and `core/node-api` against the four
ACL users and tested each one against the live server. Four gaps:

- `jobs:index` — written by the bot, not covered by the bot's key patterns.
- `jobs:running` and `jobs:complete` — written by the worker, not covered.
- `model:prediction` and `model:confidence` — read by the dashboard API, not covered. This was
  what made the dashboard crash with a permission error on the `model:*` keys.

Fixed by extending the key patterns. The nodeapi user was simultaneously narrowed to the commands
it genuinely uses — `get`, `lrange`, and `ping` — instead of the previous grab-bag. It is still
read-only: a write or a hash command is refused. The bot, worker, and ml users keep broad command
rights because they need read-write access to their own namespaces.

### Defect 4 — the dashboard container could not start under the hardening rules

The nginx image's entrypoint tries to take ownership of its cache directories, which fails when the
container runs with all capabilities dropped. The service was crash-looping with a permission
error on its cache path.

The fix keeps the security posture intact: the container now runs as the unprivileged nginx user
instead of root, and the cache and run directories are tmpfs mounts with a permissive mode so that
user can write to them. Read-only root filesystem, dropped capabilities, and no-new-privileges are
all retained. The root user was never needed here.

Note on the compose file's tmpfs syntax: the long form with a nested mode key is not accepted by
the compose version in use. The short form with the mode appended to the path is accepted and was
verified to apply the mode.

### Full stack now runs

All six services up. Redis healthy, worker healthy, dashboard API answering 200 on every ML
endpoint, dashboard UI answering 200, worker heartbeat alive with a live TTL.

### Final verification

- Every service authenticates to Redis with its own credentials and gets `PONG`.
- The read-only dashboard API is refused a write (`NOPERM` on `SET`) — least privilege holds.
- Live `chat()` and `plan_changes()` calls from inside the worker container returned `PONG` and a
  parseable plan with a `files` key.
- Container-side config confirmed: timeout 150s, max tokens 8000, model `company-coder`,
  allowed-model list containing only `company-coder`, base URL pointing at the gateway.
- `node-api` and `pca-backend` build clean inside Docker; the bot's Python modules all compile.
- The obsolete `version:` key was removed from the compose file, which silences a warning on every
  compose command.

## Notable findings

- Three separate redis ACL rules were wrong in three different ways, and none of them could be
  found by reading the template alone. The order of the deny rule, the key-pattern coverage, and
  the command set each had to be checked against the running server. The lesson for the repo is
  that the ACL template needs a test that exercises every service against the live server, not
  just a read-through.
- The dashboard's 500 and 502 responses looked like application bugs and were actually ACL
  problems. Worth remembering before reaching for the route code.
- A redis restart is required for ACL changes to take effect. The generated ACL file is written at
  startup, so an in-place template edit does nothing until the container is recreated.
- The `LITELLM ESCALATE` marker in the prompt is the upstream tier-routing hint, matching the
  gateway repo's own memory. It carries no instruction to the agent.

## Open threads

- The dashboard renders, but the ML pipeline behind it is still dormant because no data source is
  wired into `core/ml`. The endpoints return empty state rather than errors, which is the correct
  behaviour for an unwired pipeline but means the dashboard has nothing to display yet.
- Two secrets still need real values from the user before the bot can do anything end to end: the
  Telegram bot token and the allowed Telegram user id, plus a GitHub token for the pull-request
  flow. The allowed-user setting is deliberately left at zero, which denies every user rather than
  allowing everyone.
- No commit has been made for any of this work.

## Key files touched

- `redis/entrypoint.sh` — strip comments and blank lines from the generated ACL file.
- `redis/users.acl.template` — rule order corrected, key patterns extended, nodeapi command set
  narrowed to read-only.
- `docker-compose.prod.yml` — dashboard container runs as the unprivileged nginx user; cache and
  run directories are tmpfs mounts with a permissive mode.
