# ==========================
# VDB Index Layer (FAISS + Recovery Safe)
# ==========================

import faiss
import numpy as np
import os
import pickle
import threading
from typing import List, Tuple

from .models import DB_FILE, init_db, list_embeddings

INDEX_FILE = "/data/index.bin"


# --------------------------
# THREAD SAFETY LOCK
# --------------------------
_index_lock = threading.Lock()


class VDBIndex:
    """
    FAISS index manager with:
    - safe persistence
    - SQLite rebuild fallback
    - crash recovery mode
    """

    def __init__(self, dim: int = 512):
        self.dim = dim
        self.index = faiss.IndexFlatIP(dim)
        self.ids: List[str] = []

    # --------------------------
    # INITIALIZATION
    # --------------------------
    def build_from_db(self):
        """
        Loads FAISS index if available,
        otherwise rebuilds from SQLite (source of truth)
        """

        init_db()

        with _index_lock:

            if os.path.exists(INDEX_FILE):
                try:
                    with open(INDEX_FILE, "rb") as f:
                        self.index, self.ids = pickle.load(f)
                        return
                except Exception:
                    # corrupted index fallback
                    self.index = faiss.IndexFlatIP(self.dim)
                    self.ids = []

            # rebuild from DB if no index exists or corruption detected
            self._rebuild_from_db()

    # --------------------------
    # REBUILD FROM SQLITE
    # --------------------------
    def _rebuild_from_db(self):
        rows = list_embeddings(limit=10_000)

        self.index = faiss.IndexFlatIP(self.dim)
        self.ids = []

        vectors = []

        for row in rows:
            vec = np.frombuffer(row["vector"], dtype="float32")

            if vec.shape[0] != self.dim:
                continue

            self.ids.append(row["id"])
            vectors.append(vec)

        if vectors:
            self.index.add(np.array(vectors, dtype="float32"))

        self._checkpoint()

    # --------------------------
    # ADD VECTORS (SAFE WRITE)
    # --------------------------
    def add_vectors(self, ids: List[str], vectors: List[np.ndarray]) -> None:

        if len(ids) != len(vectors):
            raise ValueError("IDs and vectors length mismatch")

        with _index_lock:
            vectors_np = np.array(vectors, dtype="float32")

            self.index.add(vectors_np)
            self.ids.extend(ids)

            self._checkpoint()

    # --------------------------
    # SEARCH
    # --------------------------
    def search(self, query_vector: np.ndarray, top_k: int = 5) -> List[Tuple[str, float]]:

        with _index_lock:
            query_np = np.array([query_vector], dtype="float32")

            scores, idxs = self.index.search(query_np, top_k)

            results = []

            for score, idx in zip(scores[0], idxs[0]):
                if 0 <= idx < len(self.ids):
                    results.append((self.ids[idx], float(score)))

            return results

    # --------------------------
    # ATOMIC CHECKPOINT
    # --------------------------
    def _checkpoint(self):

        tmp_file = INDEX_FILE + ".tmp"

        try:
            with open(tmp_file, "wb") as f:
                pickle.dump((self.index, self.ids), f)

            os.replace(tmp_file, INDEX_FILE)

        except Exception as e:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
            raise RuntimeError(f"Index checkpoint failed: {str(e)}")

    # --------------------------
    # HEALTH / DEBUG
    # --------------------------
    def stats(self):
        return {
            "size": len(self.ids),
            "dim": self.dim,
            "index_type": "IndexFlatIP",
        }
