# /core/ml/config.py
# Module-level env reads + ML pipeline constants.
# Hand-written validation, no zod (per project rule).

import os

# --------------------------------------------------
# REDIS CONFIG (per-service ACL: user `ml`)
# --------------------------------------------------
REDIS_USER = os.getenv("REDIS_USER", "ml")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

# --------------------------------------------------
# ML PIPELINE CONFIG
# --------------------------------------------------

# PCA SETTINGS
PCA_COMPONENTS = 5

# DRIFT THRESHOLDS (used by ml_worker.classify_drift and risk_classifier)
DRIFT_THRESHOLD_LOW = 0.25
DRIFT_THRESHOLD_MEDIUM = 0.5
DRIFT_THRESHOLD_HIGH = 0.75

# RISK CLASS LABELS (0..3)
RISK_CLASSES = ["Low", "Medium", "High", "Critical"]

# ML LOOP INTERVAL (seconds)
ML_WORKER_SLEEP = int(os.getenv("ML_WORKER_SLEEP", "5"))

# --------------------------------------------------
# DATA SOURCE
# --------------------------------------------------
# synthetic: seeded deterministic stream; dashboard renders out of the box.
# none:      pipeline idle, only the heartbeat ticks (pre-2026-11-07 default).
# A future value (e.g. gateway) can be added without changing the loop.
ML_DATA_SOURCE = os.getenv("ML_DATA_SOURCE", "synthetic")

# Synthetic stream shape. PCA needs >= 2 samples and >= 2 features.
ML_SYNTHETIC_SAMPLES = int(os.getenv("ML_SYNTHETIC_SAMPLES", "64"))
ML_SYNTHETIC_DIM = int(os.getenv("ML_SYNTHETIC_DIM", "128"))

# --------------------------------------------------
# ORIGINAL FEATURES (pre-encoding)
# --------------------------------------------------
# Each entry describes one observable dimension before one-hot / label encoding.
# numeric:  1 output dim, sampled from N(0,1).
# onehot:   len(values) output dims, one active per sample.
# total dims across all features MUST equal ML_SYNTHETIC_DIM.
# --------------------------------------------------
ORIGINAL_FEATURES = [
    # numeric — 10 features × 1 dim = 10
    {"name": "prompt_tokens",       "type": "numeric"},
    {"name": "completion_tokens",   "type": "numeric"},
    {"name": "total_tokens",        "type": "numeric"},
    {"name": "latency_ms",          "type": "numeric"},
    {"name": "tokens_per_sec",      "type": "numeric"},
    {"name": "context_used",        "type": "numeric"},
    {"name": "context_total",       "type": "numeric"},
    {"name": "temperature",         "type": "numeric"},
    {"name": "max_tokens",          "type": "numeric"},
    {"name": "repeat_penalty",      "type": "numeric"},
    # onehot — 6 categorical × (N+1) dims = 27
    {"name": "model",               "type": "onehot",
     "values": ["gpt-4o", "gpt-4o-mini", "claude-3.5", "o1-preview", "o1-mini"]},
    {"name": "status",              "type": "onehot",
     "values": ["success", "rate_limit", "timeout", "error"]},
    {"name": "error_type",          "type": "onehot",
     "values": ["auth", "quota", "server", "invalid_request"]},
    {"name": "cache_hit",           "type": "onehot",
     "values": ["hit", "miss", "partial"]},
    {"name": "reasoning",           "type": "onehot",
     "values": ["none", "chain", "tree", "beam", "self-discover", "sketch"]},
    {"name": "output_format",       "type": "onehot",
     "values": ["json", "markdown", "plain", "code"]},
    # onehot — 10 categorical × (N+1) dims = 91
    {"name": "feature",             "type": "onehot",
     "values": ["auth", "billing", "api", "docs", "cli", "dashboard", "webhook",
                "export", "import", "search"]},
    {"name": "priority",            "type": "onehot",
     "values": ["critical", "high", "medium", "low", "backlog", "wontfix", "info"]},
    {"name": "language",            "type": "onehot",
     "values": ["python", "typescript", "go", "rust", "bash", "sql", "yaml", "json", "toml"]},
    {"name": "region",              "type": "onehot",
     "values": ["us-east", "us-west", "eu-west", "ap-south", "ca-central", "sa-east",
                "me-south", "ap-northeast", "ap-southeast", "eu-north"]},
    {"name": "environment",         "type": "onehot",
     "values": ["prod", "staging", "dev", "preview", "local", "ci"]},
    {"name": "user_tier",           "type": "onehot",
     "values": ["enterprise", "pro", "team", "hobby", "trial", "free", "internal", "partner", "education"]},
    {"name": "request_source",      "type": "onehot",
     "values": ["api", "cli", "dashboard", "webhook", "sdk", "notebook", "mobile", "batch"]},
    {"name": "file_type",           "type": "onehot",
     "values": ["py", "ts", "tsx", "js", "go", "rs", "sh", "sql", "yaml", "toml"]},
    {"name": "test_status",         "type": "onehot",
     "values": ["pass", "fail", "skip", "xfail", "error", "timeout", "crash", "leak",
                "flaky"]},
    {"name": "change_type",         "type": "onehot",
     "values": ["feature", "fix", "refactor", "perf", "docs", "test", "chore", "revert",
                "security", "breaking"]},
    {"name": "deploy_target",       "type": "onehot",
     "values": ["container", "serverless"]},
    {"name": "os_type",             "type": "numeric"},
    {"name": "cpu_pct",             "type": "numeric"},
]


def _compute_encoding_map():
    """Return (feature_names, encoding_map, total_dims)."""
    names = []
    emap = {}
    offset = 0
    for feat in ORIGINAL_FEATURES:
        name = feat["name"]
        names.append(name)
        if feat["type"] == "numeric":
            emap[name] = list(range(offset, offset + 1))
            offset += 1
        else:
            n_cats = len(feat["values"])
            emap[name] = list(range(offset, offset + n_cats))
            offset += n_cats
    return names, emap, offset


ORIGINAL_FEATURE_NAMES, ENCODING_MAP, TOTAL_ENCODED_DIMS = _compute_encoding_map()


def get_encoding_map():
    """Return a deep copy of the encoding map for use at runtime."""
    return {
        name: list(indices)
        for name, indices in ENCODING_MAP.items()
    }


# Validate at import time
expected = ML_SYNTHETIC_DIM
actual = TOTAL_ENCODED_DIMS
if actual != expected:
    raise ValueError(
        f"ORIGINAL_FEATURES encodes to {actual} dims but "
        f"ML_SYNTHETIC_DIM={expected}. Adjust the feature list to match."
    )

# --------------------------------------------------
# LOGGING
# --------------------------------------------------
ML_LOG_LEVEL = os.getenv("ML_LOG_LEVEL", "INFO")
