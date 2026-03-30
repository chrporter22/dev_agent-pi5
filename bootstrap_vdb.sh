#!/bin/bash
# bootstrap_vdb.sh
# One-command setup for OpenClaw VDB
# Initializes /data, preloads embeddings, rebuilds index, verifies NVMe persistence

set -euo pipefail

VDB_DATA_DIR="./core/vdb/data"
PRELOAD_FILE="$VDB_DATA_DIR/instructions.json"
SQLITE_DB="$VDB_DATA_DIR/db.sqlite"
FAISS_INDEX="$VDB_DATA_DIR/index.bin"

echo "===== OpenClaw VDB Bootstrap ====="

# 1. Ensure NVMe-backed data directory exists
echo "Creating VDB data directory at $VDB_DATA_DIR..."
mkdir -p "$VDB_DATA_DIR"

# 2. Check NVMe mount (basic)
NVME_DEV=$(df "$VDB_DATA_DIR" | tail -1 | awk '{print $1}')
echo "VDB volume mounted on device: $NVME_DEV"
if [[ "$NVME_DEV" != *"nvme"* ]]; then
    echo "Warning: $VDB_DATA_DIR is not on NVMe device. Performance may be impacted."
else
    echo "NVMe mount detected."
fi

# 3. Create empty SQLite DB if missing
if [[ ! -f "$SQLITE_DB" ]]; then
    echo "Creating SQLite database $SQLITE_DB..."
    sqlite3 "$SQLITE_DB" "VACUUM;"
else
    echo "SQLite DB already exists."
fi

# 4. Create empty FAISS index if missing
if [[ ! -f "$FAISS_INDEX" ]]; then
    echo "Creating placeholder FAISS index $FAISS_INDEX..."
    touch "$FAISS_INDEX"
else
    echo "FAISS index already exists."
fi

# 5. Check preload instructions file
if [[ ! -f "$PRELOAD_FILE" ]]; then
    echo "Creating default instructions.json..."
    cat > "$PRELOAD_FILE" <<EOF
[
  {
    "text": "Create a PCA CLI tool for CSV datasets",
    "metadata": {"source": "preload", "timestamp": 1710000000}
  },
  {
    "text": "Generate a data visualization dashboard",
    "metadata": {"source": "preload", "timestamp": 1710000100}
  },
  {
    "text": "Build a regression model for time-series data",
    "metadata": {"source": "preload", "timestamp": 1710000200}
  },
  {
    "text": "Perform eigenvalue decomposition on covariance matrix",
    "metadata": {"source": "preload", "timestamp": 1710000300}
  },
  {
    "text": "Summarize CSV data statistics (mean, std, min, max)",
    "metadata": {"source": "preload", "timestamp": 1710000400}
  }
]
EOF
else
    echo "Preload instructions file exists."
fi

# 6. Populate embeddings via Python script
echo "Populating embeddings from $PRELOAD_FILE..."
python3 ./core/vdb/populate_volume.py --file "$PRELOAD_FILE" --db "$SQLITE_DB" --index "$FAISS_INDEX"

# 7. Verify persistence
echo "Verifying NVMe persistence..."
SYNC_SIZE=$(du -sh "$VDB_DATA_DIR" | awk '{print $1}')
echo "VDB data directory size: $SYNC_SIZE"
ls -lh "$SQLITE_DB" "$FAISS_INDEX" "$PRELOAD_FILE"

echo "===== Bootstrap complete! VDB ready. ====="
