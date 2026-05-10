# /core/ml/drift_detector.py

import numpy as np


def compute_drift(current_embeddings):

    centroid = np.mean(
        current_embeddings,
        axis=0
    )

    variance = np.var(
        current_embeddings,
        axis=0
    )

    centroid_shift = float(
        np.linalg.norm(centroid)
    )

    variance_shift = float(
        np.mean(variance)
    )

    drift_score = (
        centroid_shift +
        variance_shift
    ) / 2

    return {
        "centroid_shift": centroid_shift,
        "variance_shift": variance_shift,
        "drift_score": drift_score
    }
