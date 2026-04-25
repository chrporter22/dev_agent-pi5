#!/bin/bash
set -euo pipefail

# ---------------------------
# MUST MATCH DOCKER VOLUME
# ---------------------------
VDB_DATA_DIR="/data"

PRELOAD_FILE="$VDB_DATA_DIR/instructions.json"
SQLITE_DB="$VDB_DATA_DIR/db.sqlite"
FAISS_INDEX="$VDB_DATA_DIR/index.bin"

echo "===== OpenClaw VDB Bootstrap ====="

# ---------------------------
# 1. ENSURE DATA DIRECTORY
# ---------------------------
mkdir -p "$VDB_DATA_DIR"

echo "Using VDB directory: $VDB_DATA_DIR"

# ---------------------------
# 2. SQLITE INITIALIZATION (REAL)
# ---------------------------
if [[ ! -f "$SQLITE_DB" ]]; then
    echo "Creating SQLite DB..."

    sqlite3 "$SQLITE_DB" <<EOF
CREATE TABLE IF NOT EXISTS embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    embedding BLOB,
    metadata TEXT
);
EOF

else
    echo "SQLite DB exists"
fi

# ---------------------------
# 3. FAISS INDEX INITIALIZATION (SAFE GUARD ONLY)
# ---------------------------
if [[ ! -f "$FAISS_INDEX" ]]; then
    echo "Creating FAISS index placeholder..."
    # NOTE: real index is created by Python layer
    touch "$FAISS_INDEX"
else
    echo "FAISS index exists"
fi

# ---------------------------
# 4. PRELOAD DATA
# ---------------------------
if [[ ! -f "$PRELOAD_FILE" ]]; then
    echo "Creating preload dataset..."

    cat > "$PRELOAD_FILE" <<EOF
[
  {"text": "Create PCA CLI tool", "metadata": {"source": "preload"}},
  {"text": "Build dashboard visualization", "metadata": {"source": "preload"}},
  {"text": "Train regression model", "metadata": {"source": "preload"}},
  {"text": "Eigen decomposition pipeline", "metadata": {"source": "preload"}},
  {"text": "CSV statistics summarizer", "metadata": {"source": "preload"}}
]
EOF
else
    echo "Preload file exists"
fi

# ---------------------------
# 5. POPULATE EMBEDDINGS
# ---------------------------
echo "Populating embeddings..."

python3 ./core/vdb/populate_volume.py \
    --file "$PRELOAD_FILE" \
    --db "$SQLITE_DB" \
    --index "$FAISS_INDEX"

# ---------------------------
# 6. VALIDATION
# ---------------------------
echo "Validating VDB state..."

ls -lh "$SQLITE_DB" "$FAISS_INDEX" "$PRELOAD_FILE"

DB_SIZE=$(du -sh "$VDB_DATA_DIR" | awk '{print $1}')

echo "VDB size: $DB_SIZE"

echo "===== VDB Bootstrap Complete ====="
