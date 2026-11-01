# Replace nginx with a Node http server and document bring-up

- **Date:** 2026-10-31 23:16
- **Developer:** opencode (company-coder)
- **Topic:** llm

## Request

Two-part follow-up to the gateway integration.

1. Replace the nginx runtime inside `pca-backend` with a Node http proxy — nginx is heavier
   than the dashboard needs.
2. Bring the repo to the point where the only remaining out-of-band action is the Telegram
   BotFather step. Add the bring-up walk-through and the full bot command list to the README.

The `LITELLM ESCALATE` marker in the user's prompt is the upstream tier-routing hint and is
ignored as a directive.

## What was done

### Runtime change: pca-backend now uses a Node http server

The pca-backend image no longer pulls `nginx:1.27-alpine` at runtime. It is a single-stage
`node:22-alpine` image that builds the React bundle and serves it with a small in-tree Node http
server. The new server uses only built-in modules (`http`, `fs`, `path`, `zlib`, `stream`) — no
new npm dependencies, no new package-lock churn.

`core/pca-backend/serve.mjs` does four things:

- Serves static files from `dist/` with a `Cache-Control` header per file type and an
  `X-Content-Type-Options: nosniff` security header.
- Falls back to `dist/index.html` for any path that is not a real file, so the React router's
  client-side navigation works on direct hits and page refreshes.
- Proxies `/api/*` to `node-api:3000` with the request method, body, and headers preserved, and
  adds `x-forwarded-host` and `x-forwarded-for` so the API knows the real origin.
- Gzips text responses when the client advertises `Accept-Encoding: gzip`.

`core/pca-backend/Dockerfile` is now a single stage:

```
FROM node:22-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
ENV NODE_API_URL=http://node-api:3000
ENV PORT=80
EXPOSE 80
CMD ["node", "serve.mjs"]
```

`core/pca-backend/nginx.conf` is deleted. `package.json` gains a `start` script that calls
`node serve.mjs`.

### Compose: pca-backend simplified

The previous pca-backend entry had to run as the unprivileged nginx user (`101:101`) with two
custom-mode tmpfs mounts (`/var/cache/nginx:mode=1777`, `/var/run:mode=1777`) because nginx's
entrypoint `chown`s its cache dir and the container is hardened with `cap_drop: ALL`. With nginx
gone, none of that is needed. The entry now matches the rest of the stack: `read_only: true`,
`/tmp` tmpfs, `cap_drop: ALL`, `no-new-privileges`. A real `healthcheck` was also added — the
previous entry had none, so Docker could only report whether the container was running, not
whether the server inside was actually serving.

### Bug found and fixed in the new server

The first cut of `serve.mjs` had a bug where `sendStatic()` returned a `boolean` from one code
path and a `Promise` from another, but its caller unconditionally treated the return value as a
`Promise`. Any request whose target file did not exist — including the SPA-fallback test
`curl http://localhost/nonexistent` — crashed the server with `TypeError: .then is not a
function`. Fixed by making `sendStatic` an `async` function that always returns a boolean, and
making the request handler `async` to `await` it.

### Bring-up documentation

The README now has a **Bring-up** section that walks the user through the four steps from a
fresh clone to a working bot:

1. Get a Telegram bot token from @BotFather.
2. Get the user's numeric Telegram id from @userinfobot.
3. Edit `TELEGRAM_TOKEN` and `ALLOWED_USER` in `.env` (the file already ships with random Redis
   passwords and a working gateway key).
4. `docker compose -f docker-compose.prod.yml up -d --build`.

The README also gets a **Bot commands** table covering every command the bot actually handles:
`/help`, `/status`, `/chat`, `/clear`, `/model`, `/build`, `/jobs`, `/job`, `/pr list`,
`/pr <url|num>`, `/pr approve <url|num>`. Anything else falls through to `/help`.

The top of `.env.example` now points the user at the BotFather step and the userinfobot step
before they read anything else.

### Cross-references updated

- `AGENTS.md` — the `pca-backend` line under "Services" now says "served by a small Node http
  server", and the `core/pca-backend` paragraph explains that the Node server does static,
  gzip, SPA fallback, and the `/api/*` proxy itself, with no new dependencies.
- The obsolete note about `pca-backend` running as uid `101` is gone from the "Docker and
  compose" section.
- The README's project-structure tree now lists `serve.mjs` and no longer lists `nginx.conf`.

## Notable findings

- The nginx chown workaround from the previous session was a workaround for the wrong choice of
  web server. Replacing nginx removed the problem at the root rather than papering over it.
- The `serve.mjs` server is small enough (≈ 200 lines including the MIME map) that adding it
  was cheaper than fighting the nginx entrypoint, even with the bug fix in between.
- The `docker-compose.prod.yml` file no longer prints a warning on every command — the obsolete
  `version: "3.9"` key was removed at the same time.
- The build still warns that the dashboard JS bundle is over 500 KB, which is a Vite code-split
  optimization for later. Not in scope for this change.

## Open threads

- No commit has been made yet for any of this work.
- The Telegram bot cannot actually be exercised end-to-end yet, because `TELEGRAM_TOKEN` and
  `ALLOWED_USER` in `.env` are still placeholders / `0`. The BotFather + userinfobot steps in
  the README are what fill those in.
- The ML pipeline behind the dashboard is still dormant (no data source wired). The dashboard
  renders empty state for that reason; this is unchanged from before.

## Key files touched

- `core/pca-backend/serve.mjs` — new. The http server.
- `core/pca-backend/Dockerfile` — rewritten as single-stage `node:22-alpine`.
- `core/pca-backend/package.json` — added `start` script.
- `core/pca-backend/nginx.conf` — deleted.
- `docker-compose.prod.yml` — pca-backend entry simplified, real `healthcheck` added.
- `README.md` — added **Bring-up** section and **Bot commands** table; updated architecture
  diagram, project structure tree, phase-4 line, and verification log description.
- `AGENTS.md` — pca-backend service line updated; nginx workaround note removed.
- `.env.example` — header now points the user at BotFather and @userinfobot.
