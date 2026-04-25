# ==========================
# OpenClaw VDB Configuration Layer
# ==========================

import os


# --------------------------
# SAFE ENV PARSING HELPERS
# --------------------------
def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _get_str(name: str, default: str) -> str:
    return os.getenv(name, default)


def _get_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "y")


# ==========================
# CORE VDB CONFIG
# ==========================
VDB_PORT = _get_int("VDB_PORT", 8081)
VDB_HOST = _get_str("VDB_HOST", "0.0.0.0")

DATA_DIR = _get_str("VDB_NVME_PATH", "/data")

# --------------------------
# SEARCH CONFIG
# --------------------------
TOP_K_DEFAULT = _get_int("VDB_TOP_K", 5)
EMBED_DIM = _get_int("VDB_EMBED_DIM", 512)

# --------------------------
# MEMORY / PERFORMANCE
# --------------------------
MAX_MEMORY_MB = _get_int("VDB_MEMORY_LIMIT_MB", 1024)
MAX_CONCURRENT_REQUESTS = _get_int("VDB_MAX_CONCURRENT_REQUESTS", 10)

# --------------------------
# FAISS CONFIG
# --------------------------
FAISS_INDEX_FILE = f"{DATA_DIR}/index.bin"
FAISS_INDEX_TYPE = _get_str("VDB_FAISS_INDEX_TYPE", "IndexFlatIP")

# --------------------------
# SQLITE CONFIG
# --------------------------
SQLITE_DB = f"{DATA_DIR}/db.sqlite"

# --------------------------
# EMBEDDING CONFIG
# --------------------------
EMBEDDING_MODEL = _get_str(
    "VDB_EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2"
)

EMBEDDING_BACKEND = _get_str("VDB_EMBEDDING_BACKEND", "local")

# --------------------------
# REDIS INTEGRATION (future ML/cache layer)
# --------------------------
REDIS_ENABLED = _get_bool("VDB_REDIS_ENABLED", True)
REDIS_HOST = _get_str("VDB_REDIS_HOST", "redis")
REDIS_PORT = _get_int("VDB_REDIS_PORT", 6379)
REDIS_PREFIX = _get_str("VDB_REDIS_PREFIX", "cache:vdb")

# --------------------------
# ML SERVICE INTEGRATION
# --------------------------
ML_SYNC_ENABLED = _get_bool("VDB_ENABLE_ML_SYNC", True)
ML_SERVICE_URL = _get_str("VDB_ML_SERVICE", "http://openclaw-ml:8080")
ML_SYNC_INTERVAL = _get_int("VDB_ML_SYNC_INTERVAL", 60)

# --------------------------
# OBSERVABILITY / DEBUG
# --------------------------
LOG_LEVEL = _get_str("VDB_LOG_LEVEL", "info")
ENABLE_METRICS = _get_bool("VDB_ENABLE_METRICS", True)
