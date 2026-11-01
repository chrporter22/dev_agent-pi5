# pca-backend is served by a small Node http server, not nginx

- **Date:** 2026-10-31
- **Decided by:** opencode (company-coder), implementing the request that nginx be replaced
- **Topic:** simplify

## Decision

The dashboard (`core/pca-backend`) is served by an in-tree Node http server, not nginx. The
server is a single file (`core/pca-backend/serve.mjs`), uses only Node built-ins (`http`, `fs`,
`path`, `zlib`, `stream`), and handles three jobs in one process: serving the React bundle with
SPA fallback, gzipping text responses, and proxying `/api/*` to `core/node-api`. There are no
new npm dependencies. The pca-backend image is a single-stage `node:22-alpine` build.

## Why

The earlier decision installed nginx as the runtime because nginx is the obvious web server.
That worked, but the hardened compose posture (read-only root, `cap_drop: ALL`,
`no-new-privileges`) collided with nginx's entrypoint `chown` of its cache directories, which
needed `CAP_CHOWN`. The previous workaround ran the container as uid 101 and mounted the cache
and run directories as mode-1777 tmpfs so that the chown step had a writable path with the
right ownership. It worked, but it was a workaround for the wrong choice of web server.

The dashboard needs three things: static files, a SPA fallback, and a `/api/*` reverse proxy.
None of those benefit from nginx's feature set. They are ~200 lines of Node built-ins, and the
result is one fewer dependency, one fewer capability conflict, and one fewer container-level
workaround (running as a non-root user). The single-stage `node:22-alpine` image is larger than
`nginx:1.27-alpine`, but the dashboard already needs Node for the Vite build, so a
multi-stage split would not have helped.

The docker-testing skill already directs verification to run inside Docker; the in-tree Node
server is what gets exercised there, not a host Node. That keeps the verification path
identical to the runtime.

## What stays

- The security posture is unchanged: `read_only: true`, `cap_drop: ALL`, `no-new-privileges`
  on the pca-backend container, with a single `/tmp` tmpfs.
- The pca-backend container remains the only public ingress (port 80). The Node server still
  proxies `/api/*` to `core/node-api` and adds `x-forwarded-host` / `x-forwarded-for`.
- The React bundle and the `core/node-api` API surface are untouched. The proxy contract from
  the frontend's perspective is unchanged.

## What changes

- New rule: `core/pca-backend` runs as root, not as the unprivileged nginx user. Running as
  uid 101 was the workaround for nginx's chown conflict, and that conflict no longer exists.
  If a future change reintroduces an entrypoint that needs to chown, it must add the
  capability back explicitly rather than restore the uid 101 trick.
- The `pca-backend` Dockerfile is a single stage. A two-stage split is no longer needed.
- The pca-backend entry in `docker-compose.prod.yml` has a real `healthcheck`. The previous
  entry had none because nginx's process being up was a sufficient signal; with the in-tree
  server, a wget healthcheck catches server crashes that used to look like "Up".

## Supersedes / relates to

- `.ai/sessions/llm/2026-10-31-2154--stack-bringup-and-redis-acl-fix.md` — the session that
  introduced the `user: 101:101` + `:mode=1777` workaround. That workaround is no longer
  needed and the session's "Defect 4" entry is superseded by this decision.
- `.ai/decisions/security/2026-10-31--redis-acls-are-enforced-per-service-boundary.md` — the
  security-posture baseline that the pca-backend container still follows. The change here
  narrows the deviation from "must run as uid 101" to "runs as root, with `read_only`,
  `cap_drop: ALL`, and `no-new-privileges` retained".
