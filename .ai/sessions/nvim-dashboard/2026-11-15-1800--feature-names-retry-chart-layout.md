# Session: feature names through pipeline + retry UI + chart layout

**Date:** 2026-11-15 17:46 (continuation)
**Topic:** pca-ui
**Status:** planning — awaiting approval

## Request

1. Put the three PCA feature-explainer bars on one line instead of stacked.
2. Add a UI control to re-run failed streams.
3. Pipe **original feature names** (pre onehot / label encoding) through the PCA pipeline so the feature-explainer shows original names, not `Dim N`.

`LITELLM ESCALATE` ignored (chat-path label).

## Plan (3 tasks)

### Task A — Chart layout (small)
- `LoadingsChart`: change `space-y-6` stack to a `grid grid-cols-1 lg:grid-cols-3` row, all three PC sections on one line at desktop width.

### Task B — Retry UI (medium)
- New `POST /api/ml/sessions/:id/retry` in `node-api/src/routes/ml.ts`:
  - Fetch job hash; verify status === `failed`.
  - Reconstruct `job_data` dict from hash fields (`chat_id`, `type`, `feature`, `text`, `session_id`, `created_at`).
  - Reset status to `queued`, clear `error`, push to `queue:jobs`, remove from `jobs:failed`, update `updated_at`.
- **ACL change**: extend `nodeapi` in `redis/users.acl.template` with `+rpush +hset +zrem` for `job:*`, `queue:*`, `jobs:*`. This expands the read-only rule for the specific retry use-case — documented as deliberate scope expansion.
- `SessionLogs.tsx`: add a `Retry` button per failed entry, `useRetrySession` mutation hook, success/error states.

### Task C — Original feature names through pipeline (large)

Goal: the 128-dim synthetic stream is built by encoding a list of named original features. PCA still runs on the encoded vector; the chart aggregates squared loadings back to original-feature level.

#### C1. `core/ml/config.py`
- Add `ML_ORIGINAL_FEATURES`: list of `{name, type, values?}`.
- `type` is `numeric` (1 dim) or `onehot` (N dims per `values`).
- Add helper `compute_encoding_map()` → returns `{name: dim_indices[]}` and `total_dims`.
- Keep `ML_SYNTHETIC_DIM` for back-compat; if total_dims != 128, log a warning. (Concrete list sums to exactly 128 — chosen so it stays simple.)

#### C2. `core/ml/ml_worker.py` — synthetic stream rewrite
- For each sample, sample per-feature values: numeric = N(0,1), categorical = uniform category.
- Apply drift on a small set of "drift-bearing" features (sinusoidal amplitude/period, replaces the old 3D latent + projection matrix).
- One-hot encode categorical; concatenate → 128-dim row.
- After PCA: store `pca:feature_names` (list of original names) and `pca:encoding_map` (dict of name → dim indices) in Redis.

#### C3. `core/ml/redis_store.py` — `pca:feature_names` / `pca:encoding_map`
- New keys added to `ml` user ACL (already covers `pca:*`).

#### C4. `core/node-api/src/routes/ml.ts`
- `/api/ml/pca/summary` reads `pca:feature_names` and `pca:encoding_map`, returns both in payload.

#### C5. Frontend types + chart
- `PcaSummary.featureNames?: string[]` (already added in last turn).
- Add `PcaSummary.encodingMap?: Record<string, number[]>` to types.
- `LoadingsChart`: when `encodingMap` is present, aggregate `sum(component[pc][dim]² for dim in encodingMap[name])` per original feature instead of per dim. Show original name as label. Falls back to per-dim when `encodingMap` is absent.

#### C6. Verify
- `docker compose -f docker-compose.prod.yml build ml node-api pca-backend`
- Curl `/api/ml/pca/summary`, confirm `feature_names` + `encoding_map` present.
- Refresh dashboard, confirm original names appear in the chart, three bars side by side, retry button works on a failed session.

## Files expected

```
M core/pca-backend/src/components/charts/LoadingsChart.tsx
M core/pca-backend/src/components/charts/SessionLogs.tsx
A core/pca-backend/src/hooks/useRetrySession.ts
M core/pca-backend/src/api/mlApi.ts
M core/pca-backend/src/types/ml.ts
M core/pca-backend/src/pages/Dashboard.tsx

M core/node-api/src/routes/ml.ts
M redis/users.acl.template

M core/ml/config.py
M core/ml/ml_worker.py
M core/ml/redis_store.py
```

## Risks

- **ACL expansion** (Task B): `nodeapi` becomes write-capable for job/queue keys. Mitigated by the retry endpoint being a single narrow operation (id validation + status check). Documented in the session.
- **Synthetic stream rewrite** (Task C2): the drift amplitude/period changes, so `drift:score` baseline shifts. Not a regression — just new seed numbers. Documented.
- **ML_SYNTHETIC_DIM mismatch**: the chosen feature list must sum to exactly 128. Verified at config-load time.

## Open questions

None yet — asking via the question tool now.
