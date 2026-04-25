# ==========================
# VDB Volume Bootstrapper (Production-safe)
# ==========================

import json
import argparse
import os
import logging
import time

from core.vdb.app.vdb import embed_and_upsert

# --------------------------
# LOGGING SETUP
# --------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

log = logging.getLogger("vdb-populator")


# --------------------------
# DEFAULT PATH
# --------------------------
DEFAULT_DATA_FILE = "/data/instructions.json"


# --------------------------
# LOAD INSTRUCTIONS
# --------------------------
def load_instructions(file_path: str):
    if not os.path.exists(file_path):
        log.warning(f"File not found: {file_path}")
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            log.error(f"Invalid JSON file: {e}")
            return []


# --------------------------
# SAFE INGESTION
# --------------------------
def ingest_entry(entry: dict, index: int, total: int):
    text = entry.get("text")
    metadata = entry.get("metadata", {})

    if not text:
        log.warning(f"Skipping empty text at index {index}")
        return None

    try:
        doc_id = embed_and_upsert(text, metadata)

        log.info(
            f"[{index}/{total}] Inserted ID={doc_id} | "
            f"text={text[:60]}"
        )

        return doc_id

    except Exception as e:
        log.error(f"Failed ingestion at index {index}: {e}")
        return None


# --------------------------
# MAIN
# --------------------------
def main():
    parser = argparse.ArgumentParser(description="Bootstrap VDB volume")
    parser.add_argument(
        "--file",
        type=str,
        default=DEFAULT_DATA_FILE,
        help="Path to instruction JSON"
    )

    args = parser.parse_args()

    instructions = load_instructions(args.file)

    if not instructions:
        log.warning("No instructions found. Exiting.")
        return

    total = len(instructions)

    log.info(f"Starting ingestion of {total} records")

    success = 0
    failed = 0

    start_time = time.time()

    for i, entry in enumerate(instructions, 1):
        result = ingest_entry(entry, i, total)

        if result:
            success += 1
        else:
            failed += 1

    duration = time.time() - start_time

    log.info("===================================")
    log.info(f"Bootstrap complete")
    log.info(f"Success: {success}")
    log.info(f"Failed: {failed}")
    log.info(f"Duration: {duration:.2f}s")
    log.info("===================================")


# --------------------------
# ENTRYPOINT
# --------------------------
if __name__ == "__main__":
    main()
