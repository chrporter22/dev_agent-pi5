# ==========================
# OpenClaw VDB API Service
# ==========================

import os
import time
import numpy as np

from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

from .vdb import embed_and_upsert, search_similar
from .models import init_db
from .db import VDBIndex

# --------------------------
# CONFIG
# --------------------------
DATA_DIR = os.getenv("VDB_NVME_PATH", "/data")

# --------------------------
# APP
# --------------------------
app = FastAPI(title="OpenClaw VDB")


# --------------------------
# EMBEDDING MODEL (READ-ONLY SERVICE LAYER)
# --------------------------
model = SentenceTransformer("all-MiniLM-L6-v2")


# --------------------------
# INDEX (shared singleton)
# --------------------------
vdb_index = VDBIndex(dim=512)


# --------------------------
# STARTUP
# --------------------------
@app.on_event("startup")
def startup():
    os.makedirs(DATA_DIR, exist_ok=True)
    init_db()
    vdb_index.build_from_db()


# ==========================
# REQUEST MODELS
# ==========================
class EmbedRequest(BaseModel):
    text: str


class UpsertRequest(BaseModel):
    text: str
    metadata: dict = {}


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


# ==========================
# ENDPOINTS
# ==========================

@app.post("/embed")
def embed(req: EmbedRequest):
    """
    Stateless embedding endpoint
    (useful for ML + worker + external services)
    """
    vec = model.encode(req.text, normalize_embeddings=True)
    return {"embedding": vec.tolist()}


@app.post("/upsert")
def upsert(req: UpsertRequest):
    """
    Full ingestion pipeline:
    text → embedding → SQLite → FAISS
    """

    doc_id = embed_and_upsert(
        text=req.text,
        metadata=req.metadata
    )

    return {
        "status": "ok",
        "id": doc_id
    }


@app.post("/search")
def search(req: SearchRequest):
    """
    Semantic search via VDB layer (FAISS + DB enrichment)
    """

    top_k = min(req.top_k, 10)

    results = search_similar(
        text=req.query,
        top_k=top_k
    )

    return {
        "matches": results
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "index_size": len(vdb_index.ids),
        "timestamp": int(time.time())
    }
