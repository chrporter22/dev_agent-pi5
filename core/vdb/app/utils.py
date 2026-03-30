# utils.py
# Tokenization, helpers, embedding generation (CPU-only)

import numpy as np
import hashlib

def embed_text(text: str, dim: int = 512):
    """
    Dummy deterministic embedding for scaffolding.
    Replace with real ARM64 CPU embedding model logic.
    Returns float32 vector of length dim.
    """
    h = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
    rng = np.random.RandomState(h % (2**32))
    vec = rng.rand(dim).astype('float32')
    # Normalize to unit vector for cosine similarity
    vec /= np.linalg.norm(vec)
    return vec
