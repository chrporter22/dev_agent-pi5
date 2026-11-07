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
    ML_WORKER_SLEEP
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

_SYNTHETIC_BASE_SEED = 42
_SYNTHETIC_LATENT_DIMS = 3
_SYNTHETIC_NOISE_STD = 0.1
_SYNTHETIC_DRIFT_AMPLITUDE = 0.5
_SYNTHETIC_DRIFT_PERIOD = 30

_cycle_counter = 0


def _load_synthetic_embeddings():
    """Persistent-RNG seeded stream for development.

    A fixed random projection matrix W is generated once.  Each cycle draws
    fresh latent values with a sinusoidal drift on the centroid, so the
    drift score oscillates smoothly instead of jumping.  RNG state is
    preserved across calls, so the draws evolve naturally cycle to cycle.
    """
    global _cycle_counter
    global _synthetic_rng
    global _synthetic_projection

    _cycle_counter += 1

    n = ML_SYNTHETIC_SAMPLES
    d = ML_SYNTHETIC_DIM

    # Lazy init: fixed projection matrix, persistent RNG
    if _cycle_counter == 1:
        _synthetic_rng = np.random.default_rng(_SYNTHETIC_BASE_SEED)
        _synthetic_projection = _synthetic_rng.standard_normal(
            (_SYNTHETIC_LATENT_DIMS, d)
        )

    rng = _synthetic_rng

    # Low-rank latent
    z = rng.standard_normal((n, _SYNTHETIC_LATENT_DIMS))

    # Sinusoidal drift on the latent centroid
    phase = 2.0 * np.pi * _cycle_counter / _SYNTHETIC_DRIFT_PERIOD
    z += _SYNTHETIC_DRIFT_AMPLITUDE * np.sin(phase)

    noise = rng.normal(0.0, _SYNTHETIC_NOISE_STD, (n, d))

    x = z @ _synthetic_projection + noise
    # Centre each batch so centroid drift is the only signal
    x -= x.mean(axis=0, keepdims=True)

    return x.astype(np.float32).tolist()


_synthetic_rng = None
_synthetic_projection = None


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
