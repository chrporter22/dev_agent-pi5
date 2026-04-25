# ==========================
# Core VDB Service Layer
# ==========================

import time
from typing import List, Dict, Any, Optional

from .db import VDBIndex
from .utils import embed_text, text_hash
from .models import insert_embedding, get_embedding


# --------------------------
# INDEX INITIALIZATION
# --------------------------
vdb_index = VDBIndex(dim=512)
vdb_index.build_from_db()


# --------------------------
# OPTIONAL HOOKS (future ML/Redis integration)
# --------------------------
def _notify_ml_pipeline(doc_id: str, vector, text: str, metadata: dict):
    """
    Hook for ML ingestion service.
    Non-blocking future extension point.
    """
    # placeholder for:
    # requests.post(openclaw-ml / redis event / queue trigger)
    pass


# --------------------------
# EMBED + UPSERT (SAFE PIPELINE)
# --------------------------
def embed_and_upsert(text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """
    Full VDB ingestion pipeline:
    text → embedding → SQLite → FAISS → ML hook
    """

    if not text:
        raise ValueError("Text cannot be empty")

    # --------------------------
    # deterministic identity (IMPORTANT)
    # --------------------------
    doc_id = text_hash(text)

    vector = embed_text(text)
    timestamp = int(time.time())

    try:
        # 1. Write to SQLite (source of truth)
        insert_embedding(
            id=doc_id,
            vector=vector.tobytes(),
            text=text,
            metadata=metadata or {},
            timestamp=timestamp
        )

        # 2. Update FAISS index
        vdb_index.add_vectors([doc_id], [vector])

        # 3. ML hook (future pipeline)
        _notify_ml_pipeline(doc_id, vector, text, metadata or {})

        return doc_id

    except Exception as e:
        # IMPORTANT: prevents silent corruption propagation
        raise RuntimeError(f"VDB upsert failed: {str(e)}")


# --------------------------
# SEARCH PIPELINE
# --------------------------
def search_similar(text: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Semantic search:
    text → embedding → FAISS → enriched results
    """

    if not text:
        return []

    vector = embed_text(text)

    raw_results = vdb_index.search(vector, top_k=top_k)

    enriched = []

    for doc_id, score in raw_results:
        row = get_embedding(doc_id)

        if not row:
            continue

        enriched.append({
            "id": doc_id,
            "score": float(score),
            "text": row["text"],
            "metadata": row["metadata"],
            "created_at": row["created_at"]
        })

    return enriched


# --------------------------
# DEBUG / HEALTH UTILITY
# --------------------------
def get_stats() -> Dict[str, Any]:
    """
    Lightweight introspection for debugging + observability
    """
    return {
        "index_size": getattr(vdb_index, "size", None),
        "dim": 512,
        "status": "healthy"
    }
