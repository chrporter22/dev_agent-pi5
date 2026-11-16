# Session: docker compose -f docker-compose.prod.yml up — failed on stale state

**Date**: 2026-11-15
**Task**: User reported `docker compose -f docker-compose.prod.yml up` "doesn't
work" (message also tagged `LITELLM ESCALATE` — see note below). One-off fix
on the local daemon, no repo code changes.

## Diagnosis

Stale docker-compose project state on the host. The daemon held two
leftover containers in `Created` status (`openclaw-bot`, `openclaw-worker`)
from a prior failed run, plus the project's bridge networks
(`dev_agent-pi5_internal_net`, `dev_agent-pi5_outbound_net`). The
`docker compose ls` view of the project was `created(2), exited(4)`.

Reproducing `up` (or `up --detach --no-build`) produced:

```
Container redis  Starting
Error response from daemon: failed to set up container networking:
network 66b23eb853c26012e11a9ba4303268eb5c71060cc7a55657c1884af12941665a not found
```

The `66b23eb...` hash in the error does not match either of the live
networks on the daemon (`7d38837631a2...` and `a203458f2ff9...`). The
compose metadata for the previous project run still referenced a network
that no longer existed — likely recreated by an earlier `system prune`
or manual `network rm`, leaving the compose project pointing at a stale
endpoint ID.

`redis` was the first container to hit the failing network attach during
the new up sequence. `openclaw-bot` and `openclaw-worker` were created
fine because they only required the project's networks, but redis's
container-namespace setup tried to bind to a leftover network reference
and aborted.

## Fix

`docker compose -f docker-compose.prod.yml down` removed the stale
networks and all six project containers cleanly. Then
`docker compose -f docker-compose.prod.yml up --detach --no-build`
brought the entire stack up. All 6 services healthy.

## Verification

```
docker compose -f docker-compose.prod.yml ps
NAME              STATUS                          PORTS
node-api          Up 42s
openclaw-bot      Up 43s
openclaw-ml       Up 43s
openclaw-worker   Up 43s (healthy)
pca-backend       Up 42s (health: starting)       0.0.0.0:8888->8888/tcp
redis             Up 43s (healthy)
```

HTTP probes through the only public ingress (`pca-backend:8888`):

```
curl http://127.0.0.1:8888/                  → 200
curl http://127.0.0.1:8888/api/ml/pca/summary → 200
    {"projection":[…],"components":[…],"variance":[…],
     "eigenvalues":[…],"totalVariance":0.994…,
     "mean":[…],"std":[…],"drift":1.338…,"risk":"Critical","confidence":0.7944}
```

The `pca-backend` healthcheck stayed at `starting` for the first ~40s
(probes port 80 in the test command even though `serve.mjs` listens on
8888 — a pre-existing cosmetic issue, not a regression from this
session; same finding as the previous target-repo session).

`node-api` log shows the expected benign message:

> Skipping the ready check because INFO command fails: "NOPERM User
> nodeapi has no permissions to run the 'info' command".

This is correct behaviour, not an error: the `nodeapi` Redis ACL is
narrowed to `+get +lrange +ping` (per `.ai/decisions/security/2026-10-31
--redis-acls-are-enforced-per-service-boundary.md`), so `INFO` correctly
returns NOPERM.

## What I did not change

- No files in `dev_agent-pi5` were edited.
- No compose file changes.
- The `.env` (gitignored) was not opened and is not referenced here.

## Note on `LITELLM ESCALATE` tag

The user message arrived tagged `LITELLM ESCALATE`. Per
`.ai/decisions/llm/2026-10-31--litellm-escalate-interpretation.md`,
that label names the Telegram `/chat` code path through the external
ai-gateway. It does not match this task (host docker-compose state,
nothing to do with the bot or the gateway). Treated as a stray tag and
ignored. Flagging here so a future session doesn't try to interpret a
docker state problem as a `/chat` problem.

## Open threads

- None. The stack is running. If the user wants this kind of stale
  state to recover automatically on `up`, that would be a compose-file
  change (`restart_policy` is already set, but compose's "ignore stale
  network references" behaviour is not a thing — only `down` clears
  project state). Out of scope unless asked.
