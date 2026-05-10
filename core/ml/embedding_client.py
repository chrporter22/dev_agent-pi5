# /core/ml/embedding_client.py

import requests
import numpy as np

from config import (
    VDB_HOST,
    VDB_PORT
)

BASE = f"http://{VDB_HOST}:{VDB_PORT}"


def fetch_embeddings():

    try:

        res = requests.get(
            f"{BASE}/embeddings"
        )

        data = res.json()

        embeddings = np.array(
            data.get("embeddings", [])
        )

        return embeddings

    except Exception as e:

        print(f"Embedding fetch failed: {e}")

        return np.array([])
