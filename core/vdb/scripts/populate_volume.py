# populate_volume.py
# Preload embeddings into NVMe-backed VDB volume
# Run this before starting your container for the first time
# Example: python populate_volume.py --file instructions.json

import json
import argparse
import os
from core.vdb.app.vdb import embed_and_upsert

DEFAULT_DATA_FILE = "/data/preload_instructions.json"

def load_instructions(file_path):
    if not os.path.exists(file_path):
        print(f"Data file {file_path} not found.")
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Expecting list of dicts: [{"text": "...", "metadata": {...}}, ...]
    return data

def main():
    parser = argparse.ArgumentParser(description="Populate VDB volume with initial embeddings")
    parser.add_argument("--file", type=str, default=DEFAULT_DATA_FILE, help="Path to JSON file containing instructions")
    args = parser.parse_args()

    instructions = load_instructions(args.file)
    if not instructions:
        print("No instructions found to preload. Exiting.")
        return

    print(f"Preloading {len(instructions)} instructions into VDB...")
    for i, entry in enumerate(instructions, 1):
        text = entry.get("text")
        metadata = entry.get("metadata", {})
        doc_id = embed_and_upsert(text, metadata)
        print(f"[{i}/{len(instructions)}] Inserted ID: {doc_id} Text: {text[:50]}...")

    print("Preload complete. All embeddings stored on NVMe.")

if __name__ == "__main__":
    main()
