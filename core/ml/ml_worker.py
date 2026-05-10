# /core/ml/ml_worker.py

import time
import numpy as np

from embedding_client import (
    fetch_embeddings
)

from pca_engine import (
    compute_pca
)

from drift_detector import (
    compute_drift
)

from risk_engine import (
    classify_risk,
    compute_probability
)

from redis_store import (
    store_json,
    store_value
)


def process_embeddings():

    embeddings = fetch_embeddings()

    if embeddings.size == 0:
        print("No embeddings available.")
        return

    # ---------------- PCA ----------------
    pca_result = compute_pca(
        embeddings
    )

    store_json(
        "pca:latest",
        pca_result["projection"]
    )

    store_json(
        "pca:components",
        pca_result["components"]
    )

    store_json(
        "pca:variance",
        pca_result["variance"]
    )

    # ---------------- DRIFT ----------------
    drift = compute_drift(
        embeddings
    )

    drift_score = drift["drift_score"]

    probability = compute_probability(
        drift_score
    )

    classification = classify_risk(
        probability
    )

    # ---------------- STORE ----------------
    store_value(
        "drift:score",
        drift_score
    )

    store_value(
        "drift:probability",
        probability
    )

    store_value(
        "drift:classification",
        classification
    )

    print(
        f"Processed embeddings | "
        f"Risk={classification}"
    )


def main():

    print("ML worker started...")

    while True:

        try:

            process_embeddings()

        except Exception as e:

            print(f"ML worker error: {e}")

        time.sleep(30)


if __name__ == "__main__":
    main()
