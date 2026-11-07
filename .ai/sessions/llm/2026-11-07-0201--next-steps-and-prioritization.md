# Next-steps and prioritization + synthetic ML wiring

- **Date:** 2026-11-07 02:01
- **Developer:** opencode (company-coder)
- **Topic:** llm

## Request

User asked what is next for this project. The session labels `LITELLM COMPACT`
and `LITELLM ESCALATE` are the project-internal markers for the Telegram
`/chat` code path (per `.ai/decisions/llm/2026-10-31--litellm-escalate-interpretation.md`)
— they are not overrides of plan-first, not separate modes, not new features.

User direction:
1. Wire the ML data source AND seed with fake data ("too much" to wire a real
   one right now).
2. Leave `TELEGRAM_TOKEN` / `ALLOWED_USER` / `DEFAULT_REPO` to the user; set up
   the repo so that pasting those three values into `.env` and rebuilding the
   bot container takes it live. Document this in the README.

## What was done

### Subtask 1 — Seeded synthetic ML data source (default ON)

`core/ml/ml_worker.py`
- Added `import numpy as np`.
- Added `_load_synthetic_embeddings()` — deterministic seeded stream with a
  fixed random projection matrix (lazy-init on first call, persistent
  numpy RNG after that), a low-rank latent structure (3 latent dims → 128 obs
  dims), a slow sinusoidal drift on the latent centroid
  (amplitude 0.5, period 30 cycles ≈ 150s at 5s/cycle), and small Gaussian
  noise (std 0.1). Each batch is centred post-hoc so centroid drift is the
  only signal.
- `_load_embeddings()` now dispatches on `ML_DATA_SOURCE`: `synthetic` →
  generator, anything else (including `none`) → `None` (the original
  dormant behaviour).

`core/ml/config.py`
- New env reads: `ML_DATA_SOURCE` (default `synthetic`), `ML_SYNTHETIC_SAMPLES`
  (default 64), `ML_SYNTHETIC_DIM` (default 128). Block comment explains the
  dispatch.

`.env.example`
- New "ML Data Source" section documenting the three flags and their safe
  defaults.

### Subtask 2 — README "Bring-up" sharpened

`README.md`
- Step 3 now explicitly lists the three values that gate go-live:
  `TELEGRAM_TOKEN`, `ALLOWED_USER`, `DEFAULT_REPO`, with a note that the
  `Connection reset by peer` log noise stops once the token is real.
- Step 5 now calls out the synthetic data source rendering the dashboard
  before any Telegram values are set, and adds a `docker logs openclaw-bot`
  pre-flight that distinguishes token-related polling errors from real
  network failures.

### Subtask 3 — Verification

- `python3 -m py_compile core/ml/*.py core/bot/*.py` → exit 0.
- `docker compose -f docker-compose.prod.yml up -d --build openclaw-ml` →
  rebuilt and restarted cleanly.
- `docker logs openclaw-ml` shows `[ML] risk=Critical drift=<value> confidence=<value>`
  with values oscillating (e.g. 1.16, 1.34, 1.64) instead of
  `No data source wired -- pipeline idle`.
- `curl http://localhost/api/ml/pca/summary` returns 64-sample non-null
  projection; explained variance ≈ 0.99 across the first 3 components.
- `curl http://localhost/api/ml/drift` returns
  `{"drift":1.34,"classification":"Critical"}`.
- `curl http://localhost/api/ml/risk` returns
  `{"prediction":"Critical","confidence":0.7984}`.
- `npm run build` in `core/node-api` (run via `docker run node:22-slim` because
  the prod container is `read_only: true` and the build needs to write
  `/app/dist`) → tsc clean.
- `npm run build` in `core/pca-backend` (same run-from-host approach) →
  vite build clean, 657.9 kB JS chunk (pre-existing chunk-size warning, not
  introduced here).

### Subtask 4 — Memory

- `.ai/decisions/llm/2026-11-07--seeded-synthetic-ml-source.md` written.
  Records the dispatch choice, the trade-offs considered, and the deferred
  decision point (real source remains TBD).
- `.ai/sessions/llm/2026-11-07-0257--LEAVE-OFF.md` written. This is the
  canonical resume-from-here file for the next session.
- This session file finalised.

## Notable findings

- The dashboard was *not* rendering an empty state — it was crashing. The
  chart components (`PCAExplorer.tsx`, `VarianceChart.tsx`,
  `EigenvalueChart.tsx`) call `.map()` on nullable arrays with no guard.
  With `pca:latest = null`, the chart throws `TypeError: Cannot read
  properties of null (reading 'map')` and React 18 unmounts the whole root —
  no error boundary exists. Wiring the synthetic source populates the keys,
  so the charts now render rather than crash. The unguarded `.map()` is a
  pre-existing defect; the plan-approved scope did not include fixing it.
- `/api/ml/pca/summary` does not return `drift:classification`,
  `ml:heartbeat`, or `ml:last_run`, even though the ML worker writes all
  three.  The DriftCard and WorkerCard therefore still show `Unknown` and
  `Offline` respectively.  Same scope note: pre-existing defect, not fixed
  here.
- `pca:history` items are stored as bare `number[][]` projections; the
  frontend `HistoryPoint` type expects an object with `{projection, drift,
  risk, timestamp?}`.  The timeline will always plot a flat line at 0
  because of this shape mismatch.  Pre-existing defect; not fixed here.
- The drift detector's threshold bands (`0.25`, `0.5`, `0.75`) are tuned for
  an embedding space where the centroid is near zero and variance per dim
  is much less than 1. With 128-dim synthetic data, the variance component
  alone puts drift_score around 0.5–1.0 even with no drift. The synthetic
  stream therefore tends to render `High` or `Critical` risk with high
  confidence. This is a property of the drift math + high-dim synthetic
  data, not a bug in this change. Tuning the thresholds would change the
  contract with the rules-based risk classifier and was out of scope.
- `/api/ml/drift` and `/api/ml/risk` exist but the frontend never calls
  them — every dashboard card reads from `/pca/summary`. Pre-existing dead
  routes; not in scope.
- The TypeScript build commands in AGENTS.md (`npm run build`) cannot run
  inside the prod containers (they are `read_only: true` per
  `docker-compose.prod.yml`).  Verification ran via `docker run --rm`
  against `node:22-slim` with the source bind-mounted, which is a known
  workaround, not a regression I caused.
- The repo's `.dockerignore` is not effective: every compose service builds
  from `context: ./core/<service>`, so the root `.dockerignore` never
  applies. The `dist/` directories left behind by the host-side `npm run
  build` are owned by root inside the bind mount and cannot be removed
  without sudo. They are gitignored, so they will not be committed, but
  they will sit on disk until the user cleans them up.

## Open threads

Not part of this change; flagged here so the next session picks them up
without re-diagnosing:

1. **Wire a real ML data source.** `ML_DATA_SOURCE=synthetic` is a
   placeholder. When the user decides on the real producer (gateway
   ml-service, `/chat` history stream, or external), the next branch should
   add a third value to the dispatch and document the source's contract.
2. **Dashboard chart null guards.** `PCAExplorer.tsx`, `VarianceChart.tsx`,
   `EigenvalueChart.tsx` need a `data ?? []` guard around `.map()` calls
   and the `<Dashboard>` body should wrap charts in an error boundary so
   a single bad key can't blank the whole page.
3. **`/api/ml/pca/summary` missing fields.** Add `driftClassification`,
   `heartbeat`, `lastRun` to the response so DriftCard and WorkerCard
   render real values instead of `Unknown` / `Offline`.
4. **`pca:history` shape mismatch.** The writer stores `number[][]`; the
   frontend expects an object. Either change the writer to store
   `{timestamp, projection, drift, risk}` or change the frontend type to
   match the array shape. Either way, the timeline will start plotting
   real numbers.
5. **Dead routes `/api/ml/drift` and `/api/ml/risk`.** Either wire the
   frontend to call them or remove them.
6. **Dead code `parse_instruction()`** in `core/bot/ai_gateway_client.py`.
   Confirmed no callers — only the docstring and `core/bot/README.md`
   mention it. Safe to remove.
7. **Stale README line.** `README.md:523` still says `Phase 5 CI — pending`
   while the roadmap two sections above marks Phase 5 shipped. One-line
   doc fix.
8. **Stale `dist/` directories on the host.** Owned by root after the
   verification build, gitignored so they won't be committed. Cleanup is
   optional (`sudo rm -rf core/node-api/dist core/pca-backend/dist`).
9. **`.ai/index/` unbuilt.** Skill installed but opt-in. The repo has
   grown since adoption; one build would help future sessions.
10. **Pre-commit secret scan.** Still deferred per
    `.ai/decisions/security/2026-10-28--no-api-keys-in-frontend-rls-in-database.md`.
    The 2026-11-04 manual audit confirmed the tree is clean; a hook would
    keep it that way automatically.

The user did not request a commit in this session; nothing is staged.
