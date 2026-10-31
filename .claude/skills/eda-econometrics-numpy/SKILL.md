---
name: eda-econometrics-numpy
description: Run EDA, PCA, and statistical drift detection with numpy primitives — no scikit-learn, no scipy in the hot path. Use when working on `core/ml` (PCA, drift, risk), when ingesting an embedding stream, when choosing `k` for PCA, or when the math in `core/ml/pca_engine.py` or `core/ml/drift_detector.py` needs to be reviewed. Triggers: "PCA", "drift score", "embedding sanity", "feature version", "numpy only", "no sklearn", "k components".
---

# EDA, PCA, and Statistical Drift with numpy

A repo-specific subset of the canonical `eda-econometrics-numpy` skill. This repo's ML pipeline (`core/ml/`) is numpy-only after the Keras/TFLite drop: it ingests an embedding matrix, runs PCA, computes a drift score, and emits a rules-based risk class. There is **no training data, no supervised model, no validation set**. The classical Kennedy assumption tests (RESET, Durbin-Watson, Breusch-Pagan, White, VIF, Jarque-Bera) do not apply and are dropped from this skill.

## The pipeline, end to end

1. **Intake.** `core/ml/ml_worker.py` polls. The current data source is unwired (`embedding_client.py` was removed along with `core/vdb`); the loop is dormant until a new source is wired. Record the data version the day a source is wired — never load the same matrix twice in the same run without an explicit reason.
2. **Sanity check.** 2D shape, `n_samples >= 2`, near-zero variance columns handled (the existing `pca_engine.py` already guards `std[std == 0] = 1.0`; do not weaken this).
3. **PCA.** Top-`k` components (`k = 5`, configurable via `config.PCA_COMPONENTS`). Persist `mean`, `components`, `explained_variance_ratio`, `eigenvalues`, `n_samples`, `n_features` to Redis.
4. **Drift.** Centroid shift + variance shift, averaged. One scalar in `[0, ∞)` — the drift score.
5. **Risk.** Rules-based classification from the drift score using `DRIFT_THRESHOLD_LOW/MEDIUM/HIGH`. No learned model.
6. **Publish.** Every output goes to Redis under the `ml` user's key patterns: `pca:*`, `drift:*`, `risk:*`, `model:*`, `ml:*`. The `nodeapi` user is read-only by command set.

The Node API and the dashboard read from there. They never recompute.

## Building blocks (numpy primitives)

Keep these in the same module as the operations that use them — `pca_engine.py` and `drift_detector.py` — so the math is read in one place:

```python
import numpy as np

def standardize(X):
    X = np.asarray(X, dtype=np.float32)
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std == 0] = 1.0
    return (X - mean) / std, mean, std
```

`pca_engine.py` already centralizes this. Reuse it; do not inline.

## PCA from numpy (preferred)

Principal component analysis is the default reduction. Use numpy. The repo currently uses `np.linalg.eigh` on the covariance matrix; the canonical skill prefers SVD on the centered data for numerical stability on ill-conditioned matrices. Both are mathematically equivalent for centered data; the SVD form is preferred when `n_samples < n_features` or when components differ greatly in magnitude:

```python
import numpy as np

def fit_pca_svd(X, n_components=5):
    X = np.asarray(X, dtype=np.float32)
    Xc = X - X.mean(axis=0)
    u, s, vt = np.linalg.svd(Xc, full_matrices=False)
    evr = (s ** 2) / (s ** 2).sum()
    k = min(n_components, vt.shape[0])
    return {
        "mean": X.mean(axis=0),
        "components": vt[:k],
        "explained_variance_ratio": evr[:k],
        "singular_values": s[:k],
    }
```

Rules:

- **Fit on the current data only.** A periodic retrain is fine; fitting inside a request handler is not. `core/ml/pca_engine.py` runs in the worker's loop, not in `node-api`.
- **Standardize first.** Mandatory when feature scales differ — the largest-magnitude feature otherwise dominates the components. `pca_engine.py` already does this.
- **Pick `k` from the explained-variance curve, not from a magic number.** The repo's `PCA_COMPONENTS = 5` is a starting point; bump or drop it when the cumulative variance curve says so, and record the choice in the session file.
- **Persist the fit.** `mean`, `components`, `explained_variance_ratio`, `eigenvalues`, `n_samples`, `n_features` are written to Redis on every loop. The dashboard reads them.
- **Reconstruction MSE** is a feature-health signal worth tracking in monitoring once data flows.
- **`sklearn.decomposition.PCA`** is not used. The `core/ml/requirements.txt` has neither `scikit-learn` nor `scipy` in the hot path.

## Drift (statistical, not learned)

`core/ml/drift_detector.compute_drift(current_embeddings)` returns a single scalar plus its components:

```python
import numpy as np

def compute_drift(X):
    centroid = np.mean(X, axis=0)
    variance = np.var(X, axis=0)
    centroid_shift = float(np.linalg.norm(centroid))
    variance_shift = float(np.mean(variance))
    drift_score = (centroid_shift + variance_shift) / 2.0
    return {
        "centroid_shift": centroid_shift,
        "variance_shift": variance_shift,
        "drift_score": drift_score,
    }
```

Rules:

- **One scalar.** The dashboard reads `drift:score` as a single number. Do not invent multi-component drift signals without first changing the contract in `core/node-api/src/routes/ml.ts` and `core/pca-backend/src/types/ml.ts`.
- **Drift is monitored, not modeled.** There is no reference distribution to compare against (no baseline window); this is the single-window centroid+variance heuristic. A proper population baseline would need a frozen reference snapshot. Note the limitation in the session file.
- **Thresholds are configurable.** `DRIFT_THRESHOLD_LOW/MEDIUM/HIGH` in `config.py`. Default 0.25 / 0.5 / 0.75. Drift is bucketed Stable / Moderate / High / Critical, and the same thresholds feed `risk_classifier.classify_risk()` for the risk label.

## Feature selection (the stage before PCA, once data flows)

When a real data source is wired, run this on the first batch — and on every batch whose distribution looks materially different:

1. **Drop near-zero variance** before PCA. A column with `std ≈ 0` destabilizes the covariance and contributes nothing.
2. **Drop near-duplicates.** Two columns with `|ρ| > 0.98` carry the same information.
3. **Winsorize heavy tails.** `|skew| > 2` gets a `log1p` or signed-log transform. Record the transform in the session file so the serving path applies the same one (when a serving path is added).
4. **Standardize** `(x − μ) / σ`. Fit on the current batch only; `pca_engine.py` already does this.
5. **PCA reduce.** Optional but recommended — `k = 5` is the default; choose from the explained-variance curve.

The current pipeline skips steps 1–3 because the data source is dormant. Keep the steps documented so they are not skipped by accident when a source is wired.

## The eval contract

This repo has no train/val/test split. The equivalent is:

- **Data version.** Recorded in the session file the day a source is wired (hash + source path).
- **Feature version.** The PCA fit artifact (mean + components + eigenvalues) — overwrite is fine because there is no held-out reference; consistency between successive fits is the signal.
- **Threshold version.** `DRIFT_THRESHOLD_*` changes go through `config.py` and the session file. The dashboard relies on the bucketed classification staying stable across small drift movements.
- **Heartbeat.** `ml:heartbeat` and `ml:last_run` are written on every cycle so the dashboard's WorkerCard reflects liveness even when the data source is empty.
- **Reporting.** Every change to `core/ml/` (PCA components, drift heuristic, risk thresholds) goes in the session file with what was measured before and after.

## When scipy / scikit-learn are acceptable

In this repo: never in the hot path. `core/ml/requirements.txt` lists only `numpy`, `redis`, `requests`. Add `scipy` only for a distribution's closed form that genuinely cannot be derived from constants, and add `scikit-learn` only for an algorithm with no honest numpy equivalent (DBSCAN with a spatial index, gradient boosting). Each new import gets a one-line comment with the reason.

## Senior-level gotchas

- **Leakage.** When the pipeline graduates to a real data source, fitting PCA on the union of train + prod and then scoring "drift" against the same union is circular. The current single-window heuristic has no leak; a windowed baseline would.
- **Drift vs. novelty.** Centroid+variance shift detects *shifts* of the distribution. It does not detect *novel points* (outliers inside an unchanged distribution). Do not sell it as anomaly detection.
- **n_components is a magic number.** The default `k = 5` came from the upstream architecture. Bump or drop it from the explained-variance curve and record the choice.
- **Risk confidence after the model drop.** `risk_classifier.classify_risk` returns `(label, confidence)` where confidence is the normalized distance from the band edge (deterministic, not learned). The dashboard multiplies it by 100. Do not present it as a learned probability.
- **"Dormant pipeline" is a known state, not a bug.** With no data source wired, the loop runs but PCA/drift/risk are skipped; the heartbeat still ticks. Tell the user this when they ask why the dashboard is empty.
- **Never invent numbers.** If a drift score, a threshold, or a model fact is not in code or memory, ask the user.

## Scope

Applies to every change in `core/ml/` and to any work that touches the embedding intake, PCA fit, drift statistic, or risk thresholds. Sits on top of `repo-memory` (which owns session/decision discipline) and `security-rbac-zero-trust` (Redis ACLs scope the `ml` user). Pairs with `docker-testing` for running the loop inside a container.
