# ==========================
# SQLite Models Layer (VDB Core)
# ==========================

import sqlite3
import json
from typing import Any, Dict, Optional, List, Tuple

DB_FILE = "/data/db.sqlite"


# --------------------------
# CONNECTION LAYER
# --------------------------
def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------
# INIT DB
# --------------------------
def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS embeddings (
        id TEXT PRIMARY KEY,
        vector BLOB NOT NULL,
        text TEXT NOT NULL,
        metadata TEXT DEFAULT '{}',
        created_at INTEGER NOT NULL
    )
    """)

    conn.commit()
    conn.close()


# --------------------------
# WRITE OPERATIONS
# --------------------------
def insert_embedding(
    id: str,
    vector: bytes,
    text: str,
    metadata: Optional[Dict[str, Any]],
    timestamp: int
) -> None:

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO embeddings
        (id, vector, text, metadata, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        id,
        vector,
        text,
        json.dumps(metadata or {}),
        timestamp
    ))

    conn.commit()
    conn.close()


# --------------------------
# READ OPERATIONS
# --------------------------
def get_embedding(id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM embeddings WHERE id = ?
    """, (id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return _row_to_dict(row)


def list_embeddings(limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM embeddings
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()

    return [_row_to_dict(row) for row in rows]


# --------------------------
# INTERNAL HELPERS
# --------------------------
def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "vector": row["vector"],
        "text": row["text"],
        "metadata": json.loads(row["metadata"] or "{}"),
        "created_at": row["created_at"]
    }
