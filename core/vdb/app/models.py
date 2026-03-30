# models.py
# SQLite ORM / data models

import sqlite3
import json
from typing import Any, Dict, Optional

DB_FILE = "/data/db.sqlite"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS embeddings (
        id TEXT PRIMARY KEY,
        vector BLOB NOT NULL,
        text TEXT NOT NULL,
        metadata TEXT,
        created_at INTEGER NOT NULL
    )
    """)
    conn.commit()
    conn.close()

def insert_embedding(id: str, vector: bytes, text: str, metadata: Optional[Dict[str, Any]], timestamp: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO embeddings (id, vector, text, metadata, created_at)
    VALUES (?, ?, ?, ?, ?)
    """, (id, vector, text, json.dumps(metadata or {}), timestamp))
    conn.commit()
    conn.close()
