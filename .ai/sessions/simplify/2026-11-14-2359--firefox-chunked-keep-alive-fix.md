# Session: Firefox NS_ERROR_NET_RESET on dashboard — Content-Length fix

**Date**: 2026-11-14
**Task**: User on Arch laptop (192.168.1.162) could not load `http://192.168.1.177:8888/`
in Firefox. F12 Network tab showed `NS_ERROR_NET_RESET`. `curl` from the same
laptop returned HTTP 200 with the full HTML, so the network and server were
fine; the symptom was Firefox-specific.

## Diagnosis

1. Memory check (per repo rules): `LITELLM ESCALATE` re-confirmed as the
   project-internal `/chat` label, not an urgency flag
   (`.ai/decisions/llm/2026-10-31--litellm-escalate-interpretation.md`).
   No workflow override.
2. `docker ps` showed `pca-backend` Up but `unhealthy` (wget healthcheck
   still probes port 80 — `.env` from 2026-11-13 port-change thread;
   separate bug, not bundled here).
3. `curl http://localhost:8888/` and `curl http://192.168.1.177:8888/`
   from the Pi both returned HTTP 200. Server reachable from the LAN IP.
4. User-side `curl -v` from the Arch laptop confirmed same — HTTP 200,
   407-byte HTML body. `Transfer-Encoding: chunked`,
   `Connection: keep-alive`, `Keep-Alive: timeout=5`.
5. F12 Network tab showed `NS_ERROR_NET_RESET` for asset requests in
   Firefox. Curl closes the connection after each response; Firefox
   keeps it open for the next request and hits the race.

**Hypothesis:** `serve.mjs` was sending static responses without
`Content-Length`, so Node fell back to chunked transfer encoding +
keep-alive. When Firefox reused the TCP connection for the next
asset, the server's keep-alive handling triggered an RST before
Firefox finished → `NS_ERROR_NET_RESET`. Curl never reuses the
connection, so it never saw the race.

## What was done

`core/pca-backend/serve.mjs` — two functions (`sendStatic`,
`sendIndex`) refactored so all response headers are assembled in a
single object and passed to `res.writeHead(200, headers)`:

- Uncompressed branch: adds `Content-Length: stat.size`. Node skips
  chunked encoding; response boundary is known up front; keep-alive
  no longer races.
- Compressed branch: adds `Content-Encoding: "gzip"` to the same
  object. Streams as before (chunked is correct here — gzipped size
  is not known until the stream runs).

While at it, moved the existing `res.setHeader("Content-Encoding",
"gzip")` calls (which ran *after* `writeHead`) into the headers
object. In the original code the call order happened to be tolerated
in some Node versions; in this Node 22-alpine image the post-writeHead
setHeader caused the `try` block in `sendStatic` to throw, the
caller's catch to swallow it, `sendIndex` to then attempt a second
`writeHead` on the same response, and `res.destroy()` to leave the
client with an empty reply. Verified by curl: with `Accept-Encoding:
gzip` the JS/CSS responses came back as "Empty reply from server"
on the first rebuild. Putting both headers in the object before
`writeHead` fixed it.

No Dockerfile, compose, or `/api/*` proxy changes. No new
dependencies. Streaming pattern preserved (no full buffering).

## Verification

| Check | Result |
|-------|--------|
| `node --check core/pca-backend/serve.mjs` | exit 0 |
| `docker compose -f docker-compose.prod.yml up -d --build pca-backend` | rebuilt clean, container Started |
| `curl -D - http://localhost:8888/` | `Content-Length: 407`, no `Transfer-Encoding` |
| `curl -D - http://localhost:8888/assets/index-CVZH7eYW.css` (no gzip) | `Content-Length: 10360`, no `Transfer-Encoding` |
| `curl -D - -H 'Accept-Encoding: gzip' .../index-CVZH7eYW.css` | `Content-Encoding: gzip`, `Transfer-Encoding: chunked`, 3248 bytes body |
| `curl -D - -H 'Accept-Encoding: gzip' .../index-CuxpqAAN.js` | `Content-Encoding: gzip`, `Transfer-Encoding: chunked`, 218383 bytes body |
| `curl http://localhost:8888/api/ml/pca/summary` | HTTP 200 — proxy still alive |
| Sequential keep-alive simulation (HTML then CSS on same connection) | both 200, no reset |

User-side verification (Firefox reload from 192.168.1.162) — pending
user confirmation.

## What's uncommitted

```
 M core/pca-backend/serve.mjs
```

Suggested commit (the user runs this, not the agent):

```bash
git add core/pca-backend/serve.mjs
git commit -m "Set Content-Length on uncompressed static responses so Firefox keep-alive no longer races"
```

HEAD at leave-off is `6d9d006` ("update go live").

## Findings the next session should not re-diagnose

- **`/api/ml/health` is at `/health`, not under `/api/ml/`.** Surfaces
  here from the 2026-11-13 LEAVE-OFF (`api/ml/health returns 404 —
  the node-api health endpoint is at /health, not under /api/ml/`).
  Not a regression.
- **Docker healthcheck still probes port 80**
  (`docker-compose.prod.yml:28` — `wget -q --spider http://localhost/`).
  Container always shows `unhealthy` after a port change to 8888, but
  is serving traffic fine. This is a separate bug from the user's
  access problem. Was identified and explicitly not bundled into this
  change. Fix is one URL: `http://localhost:8888/`.
- **`setHeader` after `writeHead` is fragile.** With this Node image
  it now throws synchronously and breaks the response. The fix here
  is to put all response headers in the headers object passed to
  `writeHead`. Worth keeping in mind for any future serve.mjs change.
- **Firefox-specific symptom.** Curl (and any client that closes
  after each response) won't show this. The original hypothesis
  (chunked + keep-alive race) is consistent with `NS_ERROR_NET_RESET`
  on the *second* request on a reused connection.
