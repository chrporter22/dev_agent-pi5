import os
import sqlite3
import json
import time
import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import faiss

DATA_DIR = "/data"
DB_PATH = os.path.join(DATA_DIR, "db.sqlite")
INDEX_PATH = os.path.join(DATA_DIR, "index.bin")

app = FastAPI()

model = SentenceTransformer("all-MiniLM-L6-v2")
dimension = 384
index = faiss.IndexFlatIP(dimension)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            id TEXT PRIMARY KEY,
            vector BLOB,
            text TEXT,
            metadata TEXT,
            created_at INTEGER
        )
    """)
    conn.commit()
    conn.close()

def load_index():
    global index
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT vector FROM embeddings").fetchall()
    conn.close()
    if rows:
        vectors = [np.frombuffer(r[0], dtype=np.float32) for r in rows]
        matrix = np.vstack(vectors)
        index.add(matrix)

@app.on_event("startup")
def startup():
    os.makedirs(DATA_DIR, exist_ok=True)
    init_db()
    load_index()

class EmbedRequest(BaseModel):
    text: str

class UpsertRequest(BaseModel):
    id: str
    text: str
    embedding: list
    metadata: dict

class SearchRequest(BaseModel):
    query: str
    top_k: int = 5

@app.post("/embed")
def embed(req: EmbedRequest):
    vec = model.encode(req.text, normalize_embeddings=True)
    return {"embedding": vec.tolist()}

@app.post("/upsert")
def upsert(req: UpsertRequest):
    vec = np.array(req.embedding, dtype=np.float32)
    index.add(np.expand_dims(vec, axis=0))

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO embeddings VALUES (?, ?, ?, ?, ?)",
        (
            req.id,
            vec.tobytes(),
            req.text,
            json.dumps(req.metadata),
            int(time.time())
        )
    )
    conn.commit()
    conn.close()

    return {"status": "ok"}

@app.post("/search")
def search(req: SearchRequest):
    top_k = min(req.top_k, 10)
    vec = model.encode(req.query, normalize_embeddings=True)
    D, I = index.search(np.expand_dims(vec, axis=0), top_k)

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id, text, metadata FROM embeddings").fetchall()
    conn.close()

    matches = []
    for idx, score in zip(I[0], D[0]):
        if idx < len(rows):
            row = rows[idx]
            matches.append({
                "id": row[0],
                "score": float(score),
                "text": row[1],
                "metadata": json.loads(row[2])
            })

    return {"matches": matches}

@app.get("/health")
def health():
    return {"status": "healthy", "index_size": index.ntotal}
