# /core/ml/ml_worker.py

import os
import time
import numpy as np
import json

from embedding_client import fetch_embeddings

from model_trainer import run_training

from pca_engine import compute_pca

from drift_detector import compute_drift

from model_runtime import RiskModel

from redis_store import (
    store_json,
    store_value,
    redis_client
)

from config import (
    ML_WORKER_SLEEP,
    ENABLE_MODEL_TRAINING
)

# --------------------------------------------------
# MODEL RUNTIME
# --------------------------------------------------
try:
    risk_model = RiskModel()

except:
    risk_model = None

TRAIN_INTERVAL = 3600  # 1 hour

last_training_time = 0

# --------------------------------------------------
# CLASS LABELS
# --------------------------------------------------

RISK_LABELS = {
    0: "Low",
    1: "Medium",
    2: "High",
    3: "Critical"
}


# --------------------------------------------------
# PROCESS PIPELINE
# --------------------------------------------------

def generate_labels(drift_score, count):

    if drift_score < 0.25:
        label = 0

    elif drift_score < 0.5:
        label = 1

    elif drift_score < 0.75:
        label = 2

    else:
        label = 3

    return np.full(
        count,
        label,
        dtype=np.int32
    )

def process_embeddings():

    embeddings = fetch_embeddings()

    # ----------------------------------
    # SAFE EMPTY STATE
    # ----------------------------------

    if embeddings is None or len(embeddings) < 2:

        print("Not enough embeddings yet")

        return

    # ----------------------------------
    # PCA
    # ----------------------------------

    pca_result = compute_pca(embeddings)

    projection = np.array(
        pca_result["projection"],
        dtype=np.float32
    )

    store_json(
        "pca:latest",
        projection.tolist()
    )
    # ----------------------------------
    # PCA HISTORY BUFFER
    # ----------------------------------

    redis_client.lpush(
        "pca:history",
        json.dumps(
            projection.tolist()
        )
    )

    # Keep latest 100 snapshots
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
    
    store_value(
        "pca:total_variance",
        pca_result["total_variance_explained"]
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
    # ----------------------------------
    # DRIFT
    # ----------------------------------

    drift = compute_drift(embeddings)

    drift_score = float(
        drift["drift_score"]
    )

    store_value(
        "drift:score",
        drift_score
    )
    # ----------------------------------
    # MODEL TRAINING
    # ----------------------------------
    global last_training_time
    global risk_model

    current_time = time.time()

    if (
        ENABLE_MODEL_TRAINING
        and current_time - last_training_time
            > TRAIN_INTERVAL
        ):

        try:

            print("[ML] Starting scheduled retraining")

            features = projection

            labels = generate_labels(
                drift_score,
                len(features)
                )

            run_training(
                features,
                labels
                )

            # Reload latest TFLite model
            risk_model = RiskModel()

            last_training_time = current_time

            print(
            "[ML] Model retrained + runtime reloaded"
            )

        except Exception as e:

            print(
                f"[TRAIN ERROR] {e}"
            )
    # ----------------------------------
    # MODEL INFERENCE
    # ----------------------------------

    latest_features = projection[-1]

    prediction = risk_model.predict(
        latest_features
    )

    prediction_id = prediction["prediction"]

    risk_label = RISK_LABELS.get(
        prediction_id,
        "Unknown"
    )

    confidence = prediction["confidence"]

    # ----------------------------------
    # STORE MODEL OUTPUTS
    # ----------------------------------

    store_value(
        "model:prediction",
        risk_label
    )

    store_value(
        "model:confidence",
        confidence
    )

    store_value(
        "risk:latest",
        risk_label
    )

    print(
        f"[ML] "
        f"Risk={risk_label} "
        f"Confidence={confidence:.4f}"
    )


# --------------------------------------------------
# MAIN LOOP
# --------------------------------------------------

def main():

    print("ML worker started...")

    os.makedirs(
        "/app/models",
        exist_ok=True
    )

    while True:

        try:

            process_embeddings()

        except Exception as e:

            print(f"[ML ERROR] {e}")

        time.sleep(
            ML_WORKER_SLEEP
        )


if __name__ == "__main__":
    main()
