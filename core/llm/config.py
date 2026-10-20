# core/llm/config.py
# --------------------------
# MODULE-LEVEL ENV READS
# --------------------------
# Per repo convention: every Python service reads os.getenv here and validates
# required values at import time. The service refuses to start if a required
# variable is missing or malformed.

import os
import sys


# --------------------------
# REQUIRED
# --------------------------
AI_GATEWAY_BASE_URL = os.getenv("AI_GATEWAY_BASE_URL")
AI_GATEWAY_API_KEY = os.getenv("AI_GATEWAY_API_KEY")
AI_GATEWAY_MODEL = os.getenv("AI_GATEWAY_MODEL")


# --------------------------
# OPTIONAL (with defaults)
# --------------------------
LLM_PORT = int(os.getenv("LLM_PORT", "8080"))
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))

# OpenAI-compatible chat completions path on the gateway.
LLM_GATEWAY_CHAT_PATH = os.getenv("LLM_GATEWAY_CHAT_PATH", "/v1/chat/completions")


# --------------------------
# VALIDATION
# --------------------------
def _require(value, name):
    if value is None or str(value).strip() == "":
        sys.stderr.write(
            f"[config] missing required env var: {name}\n"
        )
        sys.exit(1)


def _require_https_or_localhost(value, name):
    if not (value.startswith("https://") or value.startswith("http://")):
        sys.stderr.write(
            f"[config] {name} must be an http(s) URL, got: {value}\n"
        )
        sys.exit(1)


_require(AI_GATEWAY_BASE_URL, "AI_GATEWAY_BASE_URL")
_require(AI_GATEWAY_API_KEY, "AI_GATEWAY_API_KEY")
_require(AI_GATEWAY_MODEL, "AI_GATEWAY_MODEL")
_require_https_or_localhost(AI_GATEWAY_BASE_URL, "AI_GATEWAY_BASE_URL")


# --------------------------
# DERIVED
# --------------------------
# Strip trailing slash so concatenation is predictable.
AI_GATEWAY_BASE_URL = AI_GATEWAY_BASE_URL.rstrip("/")
