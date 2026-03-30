# db.py
# SQLite + FAISS index management

import faiss
import numpy as np
import os
from .models import DB_FILE, init_db
import pickle

INDEX_FILE = "/data/index.bin"

class VDBIndex:
    def __init__(self, dim: int = 512):
        self.dim = dim
        self.index = faiss.IndexFlatIP(dim)  # Cosine similarity (normalized vectors)
        self.ids = []

    def build_from_db(self):
        init_db()
        if os.path.exists(INDEX_FILE):
            with open(INDEX_FILE, "rb") as f:
                self.index, self.ids = pickle.load(f)
        else:
            self.index = faiss.IndexFlatIP(self.dim)
            self.ids = []

    def add_vectors(self, ids, vectors):
        vectors_np = np.array(vectors, dtype='float32')
        self.index.add(vectors_np)
        self.ids.extend(ids)
        self._checkpoint()

    def _checkpoint(self):
        with open(INDEX_FILE, "wb") as f:
            pickle.dump((self.index, self.ids), f)

    def search(self, query_vector, top_k=5):
        query_np = np.array([query_vector], dtype='float32')
        scores, idxs = self.index.search(query_np, top_k)
        results = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx < len(self.ids):
                results.append((self.ids[idx], float(score)))
        return results
