# vdb.py
# Core embed / upsert / search logic

import time
import uuid
from .db import VDBIndex
from .utils import embed_text
from .models import insert_embedding

vdb_index = VDBIndex(dim=512)
vdb_index.build_from_db()

def embed_and_upsert(text: str, metadata: dict):
    vector = embed_text(text)
    doc_id = str(uuid.uuid4())
    timestamp = int(time.time())
    insert_embedding(doc_id, vector.tobytes(), text, metadata, timestamp)
    vdb_index.add_vectors([doc_id], [vector])
    return doc_id

def search_similar(text: str, top_k=5):
    vector = embed_text(text)
    results = vdb_index.search(vector, top_k=top_k)
    return results
