# /core/ml/pca_engine.py

import numpy as np

from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from config import PCA_COMPONENTS


def compute_pca(embeddings):

    scaler = StandardScaler()

    normalized = scaler.fit_transform(
        embeddings
    )

    pca = PCA(
        n_components=PCA_COMPONENTS
    )

    projected = pca.fit_transform(
        normalized
    )

    return {
        "projection": projected.tolist(),
        "components": pca.components_.tolist(),
        "variance": pca.explained_variance_ratio_.tolist(),
        "mean": pca.mean_.tolist()
    }
