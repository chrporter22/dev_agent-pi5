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

from config import (
    ML_WORKER_SLEEP,
    ENABLE_PCA,
    ENABLE_DRIFT_DETECTION,
    ENABLE_MODEL_TRAINING
)

def process_embeddings():

    embeddings = fetch_embeddings()

    # ----------------------------------
    # SAFE STARTUP / EMPTY STATE GUARD
    # ----------------------------------
    if embeddings is None or embeddings.size == 0:
        print("No embeddings yet — skipping cycle")
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

# /core/ml/model_trainer.py

import numpy as np
import tensorflow as tf

from sklearn.linear_model import LogisticRegression


def train_model(features, labels):

    model = LogisticRegression(
        multi_class="multinomial",
        max_iter=1000
    )

    model.fit(features, labels)

    return model


def export_tflite():

    model = tf.keras.Sequential([
        tf.keras.layers.Dense(
            4,
            activation="softmax",
            input_shape=(2,)
        )
    ])

    converter = tf.lite.TFLiteConverter.from_keras_model(
        model
    )

    tflite_model = converter.convert()

    with open(
        "/app/models/risk_model.tflite",
        "wb"
    ) as f:
        f.write(tflite_model)
            process_embeddings()

        except Exception as e:

            print(f"ML worker error: {e}")

        time.sleep(ML_WORKER_SLEEP)


if __name__ == "__main__":
    main()
