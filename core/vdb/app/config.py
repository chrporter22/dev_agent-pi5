# config.py
# Container configs

import os

VDB_PORT = int(os.environ.get("VDB_PORT", 8081))
DATA_DIR = "/data"
MAX_MEMORY_MB = 1024
TOP_K_DEFAULT = 5
EMBED_DIM = 512
