# ==========================
# VDB Utils Layer (Scaffold + Future ML Ready)
# ==========================

import numpy as np
import hashlib
from typing import Tuple

# --------------------------
# EMBEDDING CONFIG
# --------------------------
DEFAULT_DIM = 512
EMBEDDING_VERSION = "v0.1-deterministic"


# --------------------------
# CORE EMBEDDING FUNCTION
# --------------------------
def embed_text(text: str, dim: int = DEFAULT_DIM) -> np.ndarray:
    """
    Deterministic placeholder embedding function.

    ⚠️ Replace with real model in production:
    - sentence-transformers
    - OpenAI embeddings
    - local transformer model

    Returns:
        np.ndarray: normalized float32 vector
    """

    if not isinstance(text, str) or len(text) == 0:
        raise ValueError("Text must be a non-empty string")

    # deterministic seed from text hash
    h = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
    seed = h % (2**32)

    rng = np.random.RandomState(seed)
    vec = rng.rand(dim).astype("float32")

    # --------------------------
    # SAFE NORMALIZATION
    # --------------------------
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec

    vec = vec / norm
    return vec


# --------------------------
# EMBEDDING META (IMPORTANT FOR ML EVOLUTION)
# --------------------------
def get_embedding_meta() -> dict:
    """
    Returns embedding system metadata.
    Useful for debugging + ML version tracking.
    """
    return {
        "version": EMBEDDING_VERSION,
        "dim": DEFAULT_DIM,
        "type": "deterministic_hash_projection"
    }


# --------------------------
# HASH UTIL (for Redis + dedup layer)
# --------------------------
def text_hash(text: str) -> str:
    """
    Stable hash for deduplication across:
    - Redis cache
    - VDB storage
    - worker idempotency
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
