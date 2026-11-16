# /core/ml/ml_worker.py

import json
import time

import numpy as np

from pca_engine import compute_pca
from drift_detector import compute_drift
from risk_classifier import classify_risk
from redis_store import (
    redis_client,
    store_json,
    store_value
)

from config import (
    ML_DATA_SOURCE,
    ML_SYNTHETIC_DIM,
    ML_SYNTHETIC_SAMPLES,
    ML_WORKER_SLEEP,
    ORIGINAL_FEATURES,
    ORIGINAL_FEATURE_NAMES,
    get_encoding_map
)


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def _classify_drift(score):
    """Bucket a raw drift score for the dashboard's drift card."""

    if score < 0.25:
        return "Stable"

    if score < 0.5:
        return "Moderate"

    if score < 0.75:
        return "High"

    return "Critical"


def _heartbeat():
    """Always-on liveness signals. Written every cycle, even when no data
    is available, so the dashboard's WorkerCard stays accurate."""

    now = int(time.time())

    store_value("ml:heartbeat", now)
    store_value("ml:last_run", now)


# --------------------------------------------------
# SYNTHETIC DATA SOURCE (development / bring-up)
# --------------------------------------------------
# Each cycle samples one value per ORIGINAL_FEATURE per row, encodes it
# (numeric → identity, onehot → one-hot), and concatenates the result.
# The encoding is deterministic per (cycle, row, feature) so the data shape
# is stable across cycles — only the values evolve.
# --------------------------------------------------

_SYNTHETIC_BASE_SEED = 42
_SYNTHETIC_NOISE_STD = 0.1
_SYNTHETIC_DRIFT_AMPLITUDE = 0.5
_SYNTHETIC_DRIFT_PERIOD = 30

# A handful of feature names whose onehot / numeric values carry the slow
# drift signal.  These rotate around their domain sinusoidally, so PCA
# recovers a stable latent structure with a periodic centroid shift.
_DRIFT_FEATURES = [
    "model",
    "feature",
    "priority",
    "status",
    "error_type"
]

_cycle_counter = 0
_synthetic_rng = None


def _sample_onehot(values, rng, drift_phase=0.0):
    """Pick one category.  `drift_phase` smoothly rotates the choice so
    some categories dominate at different points in the cycle."""
    n = len(values)
    if drift_phase == 0.0:
        idx = int(rng.integers(0, n))
    else:
        # Sinusoidally-biased categorical: logit = sin(phase + k*2π/n)
        logits = np.array([
            np.sin(drift_phase + k * 2.0 * np.pi / n)
            for k in range(n)
        ])
        probs = np.exp(logits - logits.max())
        probs /= probs.sum()
        idx = int(rng.choice(n, p=probs))
    out = [0.0] * n
    out[idx] = 1.0
    return out


def _sample_numeric(mean=0.0, std=1.0, drift_phase=0.0, rng=None):
    """Sample a single numeric value with optional sinusoidal mean drift."""
    effective_mean = mean + _SYNTHETIC_DRIFT_AMPLITUDE * np.sin(drift_phase)
    return float(rng.normal(effective_mean, std))


def _load_synthetic_embeddings():
    """Generate a (n × d) batch by sampling and encoding each ORIGINAL_FEATURE.

    The result is a list of lists of floats, length n rows × d cols, where
    d == ML_SYNTHETIC_DIM.  Each row represents one "observation" with
    semantically meaningful per-feature values that the dashboard can
    aggregate back to original feature names.
    """
    global _cycle_counter
    global _synthetic_rng

    _cycle_counter += 1

    if _synthetic_rng is None:
        _synthetic_rng = np.random.default_rng(_SYNTHETIC_BASE_SEED)

    rng = _synthetic_rng
    n = ML_SYNTHETIC_SAMPLES
    d = ML_SYNTHETIC_DIM

    rows = []
    phase = 2.0 * np.pi * _cycle_counter / _SYNTHETIC_DRIFT_PERIOD

    for _ in range(n):
        row = []
        for feat in ORIGINAL_FEATURES:
            name = feat["name"]
            if feat["type"] == "numeric":
                drift = phase if name in _DRIFT_FEATURES else 0.0
                row.append(_sample_numeric(drift_phase=drift, rng=rng))
            else:
                drift = phase if name in _DRIFT_FEATURES else 0.0
                row.extend(_sample_onehot(feat["values"], rng, drift_phase=drift))
        rows.append(row)

    x = np.array(rows, dtype=np.float32)

    # Light noise so PCA has a stochastic component to factor through
    noise = rng.normal(0.0, _SYNTHETIC_NOISE_STD, (n, d)).astype(np.float32)
    x = x + noise
    # Centre per batch so the drift signal sits in the mean offset
    x -= x.mean(axis=0, keepdims=True)

    return x.tolist()


# --------------------------------------------------
# SOURCE DISPATCH
# --------------------------------------------------

def _load_embeddings():
    source = ML_DATA_SOURCE

    if source == "synthetic":
        return _load_synthetic_embeddings()

    # "none" — keep the original postsimplify behaviour
    return None


# --------------------------------------------------
# MAIN LOOP
# --------------------------------------------------

def run_cycle():
    embeddings = _load_embeddings()

    if embeddings is None or len(embeddings) < 2:
        print("[ML] No data source wired -- pipeline idle")
        _heartbeat()
        return

    # ----------------------------------
    # PCA
    # ----------------------------------

    pca_result = compute_pca(embeddings)

    projection = pca_result["projection"]

    store_json(
        "pca:latest",
        projection
    )

    redis_client.lpush(
        "pca:history",
        json.dumps(projection)
    )

    redis_client.ltrim(
        "pca:history",
        0,
        100
    )

    store_json(
        "pca:components",
        pca_result["components"]
    )

    store_json(
        "pca:variance",
        pca_result["variance"]
    )

    store_json(
        "pca:eigenvalues",
        pca_result["eigenvalues"]
    )

    store_json(
        "pca:mean",
        pca_result["mean"]
    )

    store_json(
        "pca:std",
        pca_result["std"]
    )

    store_value(
        "pca:total_variance",
        pca_result["total_variance_explained"]
    )

    # ----------------------------------
    # ORIGINAL FEATURE METADATA
    # ----------------------------------
    # Names and encoding map are static across cycles (they describe the
    # synthetic schema), but we refresh them every cycle so a config change
    # is picked up on the next iteration without a worker restart.
    # ----------------------------------

    store_json(
        "pca:feature_names",
        list(ORIGINAL_FEATURE_NAMES)
    )

    store_json(
        "pca:encoding_map",
        get_encoding_map()
    )

    # ----------------------------------
    # DRIFT
    # ----------------------------------

    drift = compute_drift(embeddings)
    drift_score = float(drift["drift_score"])

    store_value("drift:score", drift_score)
    store_value("drift:classification", _classify_drift(drift_score))

    # ----------------------------------
    # RISK (rules-based, deterministic)
    # ----------------------------------

    risk_label, confidence = classify_risk(drift_score)

    store_value("model:prediction", risk_label)
    store_value("model:confidence", confidence)
    store_value("risk:latest", risk_label)

    # ----------------------------------
    # HEARTBEAT
    # ----------------------------------

    _heartbeat()

    print(
        f"[ML] risk={risk_label} "
        f"drift={drift_score:.4f} "
        f"confidence={confidence:.4f}"
    )


def main():
    print("ML worker started (numpy + rules)...")

    while True:

        try:
            run_cycle()

        except Exception as e:
            print(f"[ML ERROR] {e}")

        time.sleep(ML_WORKER_SLEEP)


if __name__ == "__main__":
    main()
