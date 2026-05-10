# /core/ml/pca_engine.py

import numpy as np

from config import PCA_COMPONENTS


# --------------------------------------------------
# PURE NUMPY PCA ENGINE
# --------------------------------------------------
# - No sklearn
# - Covariance matrix
# - Eigen decomposition
# - Top-K principal components
# - Explained variance ratios
# - Total explained variance
# --------------------------------------------------


def compute_pca(embeddings):

    # --------------------------------------------------
    # VALIDATION
    # --------------------------------------------------

    X = np.array(
        embeddings,
        dtype=np.float32
    )

    if X.ndim != 2:
        raise ValueError(
            "Embeddings must be 2D"
        )

    n_samples, n_features = X.shape

    if n_samples < 2:
        raise ValueError(
            "Need at least 2 samples for PCA"
        )

    # --------------------------------------------------
    # STANDARDIZATION
    # mean = 0
    # std = 1
    # --------------------------------------------------

    mean = np.mean(
        X,
        axis=0
    )

    std = np.std(
        X,
        axis=0
    )

    # Avoid divide-by-zero
    std[std == 0] = 1.0

    normalized = (
        X - mean
    ) / std

    # --------------------------------------------------
    # COVARIANCE MATRIX
    # shape:
    # (features x features)
    # --------------------------------------------------

    covariance_matrix = np.cov(
        normalized,
        rowvar=False
    )

    # --------------------------------------------------
    # EIGEN DECOMPOSITION
    # --------------------------------------------------
    # eigh() optimized for
    # symmetric covariance matrices
    # --------------------------------------------------

    eigenvalues, eigenvectors = np.linalg.eigh(
        covariance_matrix
    )

    # --------------------------------------------------
    # SORT DESCENDING
    # largest variance first
    # --------------------------------------------------

    sorted_indices = np.argsort(
        eigenvalues
    )[::-1]

    eigenvalues = eigenvalues[
        sorted_indices
    ]

    eigenvectors = eigenvectors[
        :,
        sorted_indices
    ]

    # --------------------------------------------------
    # SELECT TOP COMPONENTS
    # --------------------------------------------------

    k = min(
        PCA_COMPONENTS,
        eigenvectors.shape[1]
    )

    principal_components = eigenvectors[
        :,
        :k
    ]

    selected_eigenvalues = eigenvalues[
        :k
    ]

    # --------------------------------------------------
    # PROJECT DATA
    # --------------------------------------------------

    projected = np.dot(
        normalized,
        principal_components
    )

    # --------------------------------------------------
    # EXPLAINED VARIANCE
    # --------------------------------------------------

    total_variance = np.sum(
        eigenvalues
    )

    explained_variance_ratio = (
        selected_eigenvalues
        / total_variance
    )

    total_explained_variance = float(
        np.sum(
            explained_variance_ratio
        )
    )

    # --------------------------------------------------
    # RETURN SERIALIZABLE OUTPUT
    # --------------------------------------------------

    return {

        # PCA-projected embeddings
        "projection":
            projected.tolist(),

        # Eigenvectors
        "components":
            principal_components.T.tolist(),

        # Per-component variance ratio
        "variance":
            explained_variance_ratio.tolist(),

        # Total variance captured
        "total_variance_explained":
            total_explained_variance,

        # Mean vector
        "mean":
            mean.tolist(),

        # Standard deviation vector
        "std":
            std.tolist(),

        # Raw eigenvalues
        "eigenvalues":
            selected_eigenvalues.tolist(),

        # Metadata
        "n_samples":
            int(n_samples),

        "n_features":
            int(n_features),

        "n_components":
            int(k)
    }
