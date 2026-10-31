---
name: data-science
description: The actual data-science workflow for this repo — numpy-only PCA, statistical drift, rules-based risk, served via Redis to a TypeScript/Node stack. Use when working in `core/ml/`, when touching PCA/drift/risk math, or when wiring a new data source into the dormant ML loop. Triggers: "PCA", "drift score", "rules-based risk", "numpy only", "no Keras", "no TensorFlow", "TFLite drop", "embedding source".
---

# Data Science Skill — numpy-only PCA + Drift + Rules-Based Risk

This skill is repo-specific. It supersedes the generic `data-science` skill that once described a TensorFlow/Keras + FastAPI + `contract/` workflow — none of which apply to this repo after the 2026-10-24 simplify and the 2026-10-31 Keras/TFLite drop. The math here is **numpy-only**; the serving path is **Redis → Node API → React dashboard**; the model is **rules-based, not learned**.

## Operating principles

- **Start simple, prove, then add complexity.** The drift threshold ladder (0.25 / 0.5 / 0.75) plus the rules-based risk classifier is the baseline. It beats a learned model that ships late and is already what the dashboard renders.
- **Know the latency budget.** The serving path is Redis: `node-api` reads, `pca-backend` polls. Measure end-to-end render time before tuning `PCA_COMPONENTS` or the loop interval.
- **No redundant work.** The Node API is read-only over Redis — it never recomputes PCA, drift, or risk. `pca-backend` never touches Redis at all. The single source of truth is the `ml` user's key space (`pca:*`, `drift:*`, `risk:*`, `model:*`, `ml:*`).
- **Reproducible by default.** Every PCA fit writes `mean`, `components`, `explained_variance_ratio`, `eigenvalues`, `n_samples`, `n_features`. Drift and risk thresholds are constants in `core/ml/config.py` and go through the session file when they change.
- **Question the data first.** When a real data source is wired, the first batch is the provenance check. Provenance, missingness, distributions, how the embeddings were generated — these are the questions that decide whether the rest of the pipeline is meaningful.

## Workflow

1. **Read memory first.** Check `.ai/decisions/` (topic `llm`, `simplify`, `security`) and `.ai/sessions/` (topic `llm`, `ml`) before planning. The 2026-10-24 simplify decision and the 2026-10-31 ML cleanup session file are the canonical context.
2. **Plan.** State the data source, the math, the dashboard contract, and the threshold choice in the plan before coding. No Kafka-style config-driven workflow engines — direct numpy code in `core/ml/`.
3. **Intake.** One place fetches embeddings. Today that place returns `None` (the vdb source was removed). When it is wired, the intake is the only file that knows the source URL and authentication.
4. **EDA / sanity check.** Shape, near-zero variance, duplicate columns. Handled inline in `pca_engine.py` (`std[std == 0] = 1.0`, `n_samples >= 2`, 2D). Record findings in the session file.
5. **PCA.** Top-`k` components (`k = 5` default, configurable). Output to Redis under `pca:*`. Persist the artifact on every loop.
6. **Drift.** Centroid shift + variance shift, averaged. Output to Redis under `drift:*`.
7. **Risk.** Rules-based classification from the drift score (thresholds in `config.py`). Output to `model:prediction` and `model:confidence`. Confidence is the normalized band-edge distance, not a learned probability.
8. **Heartbeat.** `ml:heartbeat` and `ml:last_run` are written on every cycle so the dashboard's WorkerCard reflects liveness even when the source is empty.
9. **Validate.** When a new source is wired, run for at least one full `ML_WORKER_SLEEP` cycle and check the dashboard renders. Then check the bucket transitions: bump a synthetic drift to verify the classifier fires at the right edges.

## PCA with numpy (the working approach)

This repo's `core/ml/pca_engine.py` runs the math by computing the covariance matrix on the standardized data and taking `np.linalg.eigh`. That is mathematically correct and runs in pure numpy; the canonical `eda-econometrics-numpy` skill notes that SVD on centered data is numerically preferable for ill-conditioned matrices, but for the working `n_samples` and feature counts here, `eigh` is fine. Do not rewrite it speculatively.

Rules:

- **Fit on the current batch only.** The worker loop runs `pca_engine.compute_pca(embeddings)` inside `ml_worker.run_cycle`. No held-out reference is required because the pipeline does not train a supervised model.
- **Standardize first.** Mandatory when feature scales differ. `pca_engine.py` already does this.
- **Pick `k` from the explained-variance curve.** `PCA_COMPONENTS = 5` is the default; bump or drop from the curve and record the choice in `config.py` + the session file.
- **Persist every fit.** All six output fields are written to Redis on every cycle. The Node API reads them as the dashboard's source of truth.
- **`sklearn.decomposition.PCA`** is not used. `core/ml/requirements.txt` does not list `scikit-learn` or `scipy`.

## Drift + risk (the post-Keras layer)

After the Keras/TFLite drop, `core/ml/ml_worker.py` no longer trains a model. The risk classification is `core/ml/risk_classifier.classify_risk(drift_score)`:

- Bucketed by thresholds: `[0, 0.25)` → Low, `[0.25, 0.5)` → Medium, `[0.5, 0.75)` → High, `[0.75, ∞)` → Critical.
- Confidence is the normalized distance from the band edge (deterministic, in `[0.5, 1.0]`). It is a rule margin, not a learned probability.
- The dashboard reads `model:prediction` and `model:confidence` via `core/node-api/src/routes/ml.ts`. Those keys are produced by the ML worker and consumed read-only by the Node API.

The Redis ACLs enforce the boundary: the `ml` user produces, the `nodeapi` user reads, `default` is off. See `security-rbac-zero-trust` for the full posture.

## Serving to the TypeScript/Node stack

The serving path is **Redis → Node API → React dashboard**. No FastAPI, no pydantic, no shared `contract/` folder.

- `core/ml` writes to Redis. It is a worker loop, not an HTTP service. It has no exposed ports.
- `core/node-api` is an Express/TypeScript read-only layer over Redis. Hand-written validation, no zod. It mirrors the Redis key shape to a JSON response. The ML keys it reads are listed under `REDIS_PASSWORD_NODEAPI` in the per-service ACL.
- `core/pca-backend` is a React + Vite + Recharts dashboard, served by nginx on the only public port (80). It polls `/api/ml/*` and renders. It never touches Redis directly.
- Contract changes start in `core/pca-backend` (the consumer). `core/node-api` updates its route handlers and the `core/pca-backend/src/types/ml.ts` to match. The two repos are not cloned side-by-side; this is a single repo with three services.

There is no `core/llm` and no `core/vdb` (deleted 2026-10-24). Do not reintroduce them.

## Reference stack and libraries

- **Math:** `numpy` only. No `scipy`, no `scikit-learn`, no `pandas`. The arithmetic here is small enough that numpy primitives win on clarity and dependency surface.
- **Storage:** `redis` (Python client). One user, `ml`, scoped by `redis/users.acl.template`.
- **Serving:** `core/node-api` is Express + `ioredis`. Hand-written validators; no zod, no pydantic.
- **Dashboard:** React + Vite + Recharts + Tailwind. TypeScript strict mode.
- **Artifacts:** Each cycle writes a fresh PCA fit to Redis. No on-disk model files. The `/app/models` directory created by `core/ml/Dockerfile` is no longer needed — see Phase 4.

## Senior-level gotchas

- **Dormant pipeline is a known state, not a bug.** With no data source wired, the loop runs and skips PCA/drift/risk. `ml:heartbeat` and `ml:last_run` still tick. The dashboard's WorkerCard stays Healthy; the PCA / Drift / Risk cards show whatever was last written (or nothing).
- **Rules-based risk is not anomaly detection.** Centroid+variance shift detects *shifts* of the distribution. It does not detect *novel points*. Do not sell it as anomaly detection.
- **Risk confidence is a rule margin.** `(0.5, 1.0]` from the band-edge distance. Multiplying by 100 in the dashboard's `RiskCard` reads as a percentage but is a rule-side metric, not a learned probability.
- **Drift vs. novelty vs. outlier.** A baseline window would let us catch drift against a frozen reference; the current heuristic is single-window. A future enhancement would store a snapshot and compare.
- **Re-running a cycle is not a regression test.** Determinism is rule-based, not snapshot-based. If you need a regression test, capture a synthetic input + expected output and run it in `py_compile` mode — there is no pytest harness in this repo, by AGENTS.md design.
- **Never invent numbers.** If a threshold, a drift score, or a model fact is not in code or memory, ask the user.
- Record confirmed modeling decisions immediately in `.ai/decisions/`, the moment the user confirms them, per the `repo-memory` skill.
