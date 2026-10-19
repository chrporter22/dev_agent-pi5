---
name: data-science
description: Full-stack data science workflow for Python and TensorFlow — data intake, EDA, preprocessing, feature engineering, modeling, evaluation, serving, and monitoring — plus PCA, drift detection, and low-latency serving to a TypeScript/Node stack. Use when working on ML, PCA, model training, drift, or risk work in this repo. Triggers: "train a model", "PCA", "drift", "features", "model serving", "data pipeline", "tflite", "keras".
---

# Data Science Skill — Full-Stack Python + TensorFlow

Act as a senior data scientist in this repo. The workflows below cover the whole lifecycle — intake, modeling, serving — and push predictions to the TypeScript/Node stack as low-latency, non-redundant microservices. They sit on top of the mandatory rules in `AGENTS.md` (plan first, single agent, memory discipline) and the engineering standards there.

## Operating principles

- **Start simple, prove, then add complexity.** A baseline beats a beautiful model that ships late. Only escalate to deep models when the baseline cannot hit the target.
- **Know the latency budget.** Measure tail latency of the serving path before optimizing. Optimize what the measurements blame, not what "looks slow".
- **No redundant work.** Never recompute what is cached, re-fit what has a versioned artifact, or re-derive what the API contract already defines. Reuse beats duplicate.
- **Reproducible by default.** Seeds, data version, feature version, model version, canned eval set — every experiment reproducible.
- **Question the data first.** A senior data scientist distrusts the data until it is understood: provenance, missingness, distributions, and how it was generated.

## Workflow

1. **Read memory first.** Check `.ai/decisions/` and `.ai/sessions/` for `data`, `ml`, `pca`, `model` topics before planning. Never re-litigate settled decisions.
2. **Plan.** State the problem, the target metric, the latency budget, and the simple-baseline choice in the plan before coding.
3. **Intake.** One ingestion module (or service) pulls raw data once; record the data version.
4. **EDA.** Distributions, missingness, correlations, class balance. Write findings to the session file.
5. **Preprocessing.** One pipeline, reusable and versioned. Fit transforms on training folds only — no leakage.
6. **Feature engineering.** Feature definitions live in one place (feature module/store). The full-stack rule still applies: share what genuinely repeats, duplicate what does not.
7. **Modeling.** Baseline first; TensorFlow/Keras when needed. Keep models small for the latency target (quantize, prune, drop layers before scaling work).
8. **Evaluation.** Realistic eval protocol: proper train/val/test split, leakage-free transforms, metric matched to the business goal (not accuracy for imbalanced data).
9. **Serve.** Deploy as a stateless microservice that loads artifacts once at startup; contract-first API consumed by the Node backend.
10. **Monitor.** Log prediction latency (repo structured logging: `{ requestId, userId, action }`), track feature drift, and have a rollback path.

## PCA with numpy

Principal component analysis is the default dimensionality-reduction tool when the goal is speed, not inference. Prefer numpy SVD over a hand-rolled covariance eigendecomposition — it is numerically stable and keeps an sklearn dependency out of hot paths:

```python
import numpy as np

def fit_pca(X, n_components=None, target_variance=0.95):
    X = np.asarray(X, dtype=np.float32)
    X = (X - X.mean(axis=0))                       # center; standardize if scales differ
    u, s, vt = np.linalg.svd(X, full_matrices=False)
    evr = (s ** 2) / (s ** 2).sum()                # explained variance ratios
    k = n_components or int((np.cumsum(evr) >= target_variance).argmax()) + 1
    return {"mean": X.mean(axis=0), "components": vt[:k], "explained_variance": evr[:k]}

def apply_pca(fit, X):
    X = np.asarray(X, dtype=np.float32)
    return (X - fit["mean"]) @ fit["components"].T
```

Rules for PCA use:

- **Fit on training data only**; apply the same fitted transform to val/test/prod. Fitting on the full dataset is leakage.
- **Standardize** (unit variance) first when feature scales differ, or the largest-magnitude features dominate the components.
- Choose `k` from the explained-variance curve (e.g. 95%), not an arbitrary dimension count.
- The fitted transform is an **artifact**: persist mean + components once, load at service startup, never re-fit per request.
- numpy is preferred for inference-time transforms. `sklearn.decomposition.PCA` is fine for offline exploration and training.

## Low-latency and non-redundancy checklist

- **Load artifacts at startup**, never per request: fitted PCA/scalers, vocabularies, model weights.
- **Vectorize with numpy**; use float32 for inference. No Python loops over large arrays in hot paths.
- **Batch offline scoring**; keep online inference lean — small model, precomputed per-tenant features.
- **Cache consciously:** identical requests or repeated computations served from cache; invalidate when the data/feature/model version changes.
- **One preprocessing pipeline** shared by train and serve, so train/serve skew is impossible.
- **Avoid redundant ETL:** a feature store or materialized views mean the pipeline never recomputes the same feature in N places.
- **Profile before optimizing.** Use the repo's logging to measure p50/p95/p99; optimize what the data blames.

## Serving to the TypeScript/Node stack

- Data science ships as an internal **microservice** (e.g. FastAPI) exposing REST endpoints the Node backend calls.
- **Contract-first, aligned with this repo:** request/response schemas live in the shared `contract/` (frontend repo owns it, backend mirrors it). The Python service mirrors that contract with pydantic models — the same discipline as zod on the TS side. Never let the Python API drift from the contract.
- The service is **stateless and horizontally scalable**; model versions pinned via a registry or artifact store.
- **Environments** via env config (dev/prod), matching repo conventions. No secrets or model paths hardcoded.
- Structured logging with per-endpoint latency metrics; tenant-scoped where multi-tenant, using the `x-org-id` convention.

## Reference stack and libraries

- **Preprocessing / EDA:** numpy, pandas, scipy, scikit-learn.
- **Modeling:** TensorFlow / Keras (Sequential or functional API), trained with a fixed seed.
- **Service:** FastAPI (pydantic for contract validation, structlog/JSON logging) or TensorFlow Serving when a dedicated inference endpoint is warranted.
- **Artifacts:** model plus fitted transforms saved with versioned filenames (e.g. `v<YYYY-MM-DD>-<run>`), alongside the matching `.ai/` session and decision records.

## Senior-level gotchas

- **Leakage** is the most common silent error: any transform using the full dataset (PCA fit, scaling, imputation) inflates eval metrics. Fit on train only.
- **Imbalanced targets:** report precision/recall/AUC, never accuracy alone.
- **Drift:** a model that wins at eval can rot in prod. Track input distributions; alert on drift before accuracy complaints arrive.
- **"Works in prod once" is not done.** Add monitoring and a rollback before deploy.
- **Never invent numbers.** If a metric, baseline, or data fact is not in code or memory, ask the user.
- Record confirmed modeling decisions immediately in `.ai/decisions/`, the moment the user confirms them, per the `repo-memory` skill (`.claude/skills/repo-memory/SKILL.md`).
