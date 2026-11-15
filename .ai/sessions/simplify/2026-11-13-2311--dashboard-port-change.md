# Session: Dashboard port change 80 → 8888

**Date**: 2026-11-13
**Task**: Change pca-backend public port from 80 to 8888, rebuild container, verify.

## What was done

1. Changed `docker-compose.prod.yml` port mapping from `80:80` to `8888:8888`.
2. Updated `core/pca-backend/Dockerfile`: `ENV PORT=8888`, `EXPOSE 8888`.
3. Updated `core/pca-backend/serve.mjs`: default fallback from `"80"` to `"8888"`.
4. Updated docs: `AGENTS.md` and `README.md` port references (multi-line edits).
5. Rebuilt and restarted pca-backend container (`docker compose -f docker-compose.prod.yml up -d --build pca-backend`).
6. Verified: `curl http://localhost:8888/` → HTTP 200, `docker ps` shows healthy, port mapping `0.0.0.0:8888->8888/tcp`.

## Verification results

- Server listens on `0.0.0.0:8888` and `[::]:8888`
- Static assets serve correctly (index.html, JS, CSS all 200)
- `/api/*` reverse proxy to `node-api:3000` is active (confirmed via logs)
- `curl http://192.168.1.177:8888/` from Pi itself returns 200
- No firewall (ufw/firewalld/nftables all inactive)
- API health note: `/api/ml/health` returns 404 — the node-api health endpoint is at `/health`, not under `/api/ml/`. The `/api/ml/*` routes (summary, history, drift, risk, etc.) are mounted correctly at `router.get("/pca/summary")` etc. under the `/api/ml` prefix in `index.ts:15`. Not a regression.

## Open / unresolved

- User reports "still not showing" when accessing `http://192.168.1.177:8888/` from Firefox on another LAN device. Diagnostics show no firewall, port properly published, server responding to LAN IP from local curl. Likely causes to suggest: router AP isolation / client isolation, Firefox HTTPS-only mode, or device on different subnet. User asked for debugging steps.