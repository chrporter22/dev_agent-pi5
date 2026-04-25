import requests
import time
import random
from typing import Dict, Any
from config import LLM_ENDPOINT


# ---------------------------
# CONFIG
# ---------------------------
TIMEOUT = 10
MAX_RETRIES = 3
BACKOFF_BASE = 0.5


# ---------------------------
# SUPPORTED OUTPUT TARGETS
# ---------------------------
SUPPORTED_LANGUAGES = {
    "node",
    "react",
    "tailwind",
    "css",
    "html5",
    "c++",
    "bash",
    "python",
    "javascript",
    "typescript",
    "nextjs",
    "expressjs",
    "vite"
}

# optional alias normalization (LLMs are messy)
ALIASES = {
    "ts": "typescript",
    "js": "javascript",
    "reactjs": "react",
    "nodejs": "node",
    "express": "expressjs",
    "next": "nextjs"
}


REQUIRED_FIELDS = {
    "type",
    "language",
    "features",
    "description"
}


# ---------------------------
# HELPERS
# ---------------------------
def _normalize_language(lang: str) -> str:
    if not isinstance(lang, str):
        return lang
    return ALIASES.get(lang.lower(), lang.lower())


def _is_valid_schema(data: Dict[str, Any]) -> bool:
    return isinstance(data, dict) and REQUIRED_FIELDS.issubset(data.keys())


def _validate(data: Dict[str, Any]) -> Dict[str, Any]:
    if not _is_valid_schema(data):
        missing = REQUIRED_FIELDS - set(data.keys())
        raise ValueError(f"Invalid LLM schema. Missing fields: {missing}")

    # normalize language BEFORE validation
    lang = _normalize_language(data.get("language"))

    if lang not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Unsupported language/framework: {data.get('language')} → normalized to {lang}"
        )

    data["language"] = lang

    # features can be flexible but must not be empty
    if not data.get("features"):
        raise ValueError("Features cannot be empty")

    return data


def _request_llm(payload: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.post(
        LLM_ENDPOINT,
        json=payload,
        timeout=TIMEOUT
    )

    response.raise_for_status()

    try:
        return response.json()
    except Exception:
        raise ValueError(f"LLM returned invalid JSON: {response.text[:300]}")


# ---------------------------
# PUBLIC API
# ---------------------------
def parse_instruction(instruction: str) -> Dict[str, Any]:
    """
    Sends instruction to LLM and returns structured code-generation plan.
    """

    payload = {"instruction": instruction}

    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            data = _request_llm(payload)
            return _validate(data)

        except Exception as e:
            last_error = e

            sleep_time = BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 0.25)
            time.sleep(sleep_time)

    raise RuntimeError(
        f"LLM failed after {MAX_RETRIES} retries: {str(last_error)}"
    )
