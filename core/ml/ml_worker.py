# /core/ml/ml_worker.py

import json
import time

from pca_engine import compute_pca
from drift_detector import compute_drift
from risk_classifier import classify_risk
from redis_store import (
    redis_client,
    store_json,
    store_value
)

from config import ML_WORKER_SLEEP


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


def _load_embeddings():
    """Data source is currently unwired (the vdb source was removed along
    with `core/vdb` in the 2026-10-24 simplify). When a source is wired,
    replace this stub with the actual fetch.
    """

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
