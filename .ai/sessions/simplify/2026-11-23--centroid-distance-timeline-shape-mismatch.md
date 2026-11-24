# Session: fix centroid distance timeline — writer/reader shape mismatch

**Date**: 2026-11-23 (UTC 2026-11-24)
**Task**: Centroid Distance History timeline on pca-backend dashboard rendered as a flat line at 0. Diagnose and fix.

## Root cause

Shape mismatch between writer and reader on the `pca:history` Redis list.

- **Writer** (`core/ml/ml_worker.py`): `redis_client.lpush("pca:history", json.dumps(projection))` — stored bare `number[][]` (the PCA projection matrix only).
- **Reader** (`core/pca-backend/src/components/charts/HistoryTimeline.tsx`): expected `HistoryPoint[]` objects with `{timestamp, projection, drift, risk}` fields per the `HistoryPoint` type in `core/pca-backend/src/types/ml.ts`.

When the frontend did `centroidL2Norm(item.projection)`, `item.projection` was `undefined` on every entry, so the function returned 0 (its null-guard branch) and every chart point sat at zero. The line rendered, but with no data.

## Fix

Two changes, both minimal:

1. **`core/ml/ml_worker.py`** — proper fix. Push a structured `HistoryPoint` to `pca:history` instead of a bare projection.
   - Push initial record at PCA time (timestamp + projection; drift/risk null placeholders).
   - After drift/risk are computed, overwrite the head entry via `LSET 0` with the complete record.
   - Reuses the existing `ltrim 0 100` cap.
   - No Redis ACL change required: `ml` user already has `+@all` (minus dangerous commands), so `LSET` is included.

2. **`core/pca-backend/src/components/charts/HistoryTimeline.tsx`** — defensive fix. Normalize each history entry before processing.
   - If entry is a bare `number[][]` (legacy data already in Redis, or older worker version), wrap it as `{projection: entry}`.
   - If entry is a `HistoryPoint`, pass through.
   - Otherwise (malformed), fall back to empty projection so the chart renders no data instead of crashing.
   - This handles any pre-existing entries in `pca:history` that the new worker shape hasn't yet displaced.

## What I deliberately did not do

- Did not change `core/node-api/src/routes/ml.ts` — the route returns whatever Redis has, and the frontend now tolerates both shapes. Keeping the route shape-agnostic preserves the read-only split between `nodeapi` and `ml`.
- Did not add a backend transform in `node-api` — that would couple a read-only service to writer logic, contradicting the read-only-by-command-set ACL on `nodeapi`.
- Did not migrate legacy `pca:history` entries — they are dormant data on tmpfs and will roll out within ~100 cycles once the worker becomes active. The defensive frontend handles them in the meantime.

## Verification

- `docker compose -f docker-compose.prod.yml build node-api pca-backend` — both built (tsc + vite, no errors).
- `docker exec node-api npx tsc --noEmit` — clean (no node-api changes, but re-confirmed).
- `docker compose -f docker-compose.prod.yml up -d node-api pca-backend` — services healthy.
- `curl http://localhost:8888/api/ml/pca/history` — returns bare `number[][]` (legacy data still present, exactly the case the defensive fix handles).
- `curl http://localhost:8888/` → 200, `<title>Dev Agent PI5 Dashboard</title>`.

## Files changed

```
M core/ml/ml_worker.py
M core/pca-backend/src/components/charts/HistoryTimeline.tsx
```

## Note

The `core/ml/` data source remains unwired (dormant loop). The worker change is dormant-correct: it only runs when `_load_embeddings()` returns a non-empty batch. The timeline will populate the next time a data source is wired in. Until then, the chart shows nothing (which is the correct empty state), not a flat-zero line.
