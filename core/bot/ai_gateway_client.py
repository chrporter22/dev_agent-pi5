import json
import random
import time
from typing import Any, Callable, Dict, List, Optional

import requests

from config import (
    AI_GATEWAY_ALLOWED_MODELS,
    AI_GATEWAY_API_KEY,
    AI_GATEWAY_BASE_URL,
    AI_GATEWAY_MAX_TOKENS,
    AI_GATEWAY_MODEL,
    AI_GATEWAY_TIMEOUT
)

# ============================================================================
# AI GATEWAY CLIENT — core/bot/ai_gateway_client.py
# Thin HTTP client for the external ~/ai-gateway LiteLLM endpoint.
# Public API: parse_instruction, chat, plan_changes.
# ============================================================================

# ----------------------------------
# CONFIG
# ----------------------------------
TIMEOUT = AI_GATEWAY_TIMEOUT
MAX_RETRIES = 3
BACKOFF_BASE = 0.5

GATEWAY_CHAT_PATH = "/v1/chat/completions"
GATEWAY_MODELS_PATH = "/v1/models"
SESSION_HEADER = "x-session-id"

_MODEL_CACHE: Dict[str, Any] = {"model": None, "fetched_at": 0.0}
_MODEL_CACHE_TTL = 3600


def _discover_gateway_model() -> Optional[str]:
    url = f"{AI_GATEWAY_BASE_URL.rstrip('/')}{GATEWAY_MODELS_PATH}"
    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {AI_GATEWAY_API_KEY}"},
            timeout=10
        )
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    available = {
        m.get("id") for m in data.get("data", [])
        if isinstance(m, dict) and m.get("id")
    }
    for candidate in AI_GATEWAY_ALLOWED_MODELS:
        if candidate in available:
            return candidate
    return None


def _resolve_model() -> str:
    now = time.time()
    cached = _MODEL_CACHE.get("model")
    if cached and (now - _MODEL_CACHE["fetched_at"]) < _MODEL_CACHE_TTL:
        return cached

    discovered = _discover_gateway_model()
    if discovered:
        _MODEL_CACHE["model"] = discovered
        _MODEL_CACHE["fetched_at"] = now
        return discovered

    return AI_GATEWAY_MODEL or "company-coder"


# ----------------------------------
# ERRORS
# ----------------------------------
class GatewayHttpError(RuntimeError):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code



# ----------------------------------
# SYSTEM PROMPTS
# ----------------------------------
PARSE_SYSTEM_PROMPT = (
    "You are a code-generation planner. Given a feature request, "
    "return a JSON object with the following fields:\n"
    "- type: the type of task (\"code_gen\", \"refactor\", \"config\", \"docs\")\n"
    "- language: the primary language or framework\n"
    "- features: a list of feature components to build\n"
    "- description: a short summary of what to build\n\n"
    "Return ONLY valid JSON, no markdown, no explanation."
)

CHAT_SYSTEM_PROMPT = (
    "You are a concise coding assistant. Answer the user's questions "
    "about code, debugging, and architecture in plain prose. "
    "Use fenced code blocks for snippets. Keep replies under 1500 words."
)

PLAN_CHANGES_SYSTEM_PROMPT = (
    "You are a code-generation planner for a git repository. "
    "Given a feature instruction and the repo context, return a JSON object "
    "with this exact shape:\n"
    '{\n'
    '  "files": [\n'
    '    {"path": "relative/path/to/file", '
    '"action": "create|modify|delete", '
    '"content": "full file contents"}\n'
    '  ]\n'
    '}\n\n'
    "Rules:\n"
    "- Use 'create' for new files, 'modify' for existing files (provide full new content), "
    "'delete' for removals.\n"
    "- The repo context includes a 'conventions' field with the target repo's "
    "AGENTS.md, CLAUDE.md, .ai/decisions/ (file list + first line per file), "
    ".ai/sessions/ (file list + first line per file), and .github/workflows/ "
    "(full content of each workflow file) when those paths exist. When present, "
    "follow those conventions for file layout, naming, style, and workflow patterns.\n"
    "- Only reference file paths that appear in the 'files' list of the repo "
    "context, or paths you are creating or modifying in this change. Never invent "
    "paths.\n"
    "- If the repo already has .github/workflows/*.yml files, extend or modify "
    "one of them to cover the new change, following the same style. Do not "
    "create a new workflow file if an existing one is the right place.\n"
    "- If the repo has no workflows, create one that matches the repo's actual "
    "structure (derive build and test commands from the 'files' list and "
    "'conventions', not from assumptions about a default layout).\n"
    "- Return ONLY valid JSON, no markdown, no explanation."
)


# ----------------------------------
# PRIVATE HELPERS
# ----------------------------------
_VALID_JSON_ESCAPES = set('"\\/bfnrt')


def _strip_code_fence(text: str) -> str:
    """Remove a leading markdown fence and anything after its closing fence."""
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    body = lines[1:]

    for i, line in enumerate(body):
        if line.strip().startswith("```"):
            body = body[:i]
            break

    return "\n".join(body)


def _repair_json_escapes(text: str) -> str:
    """Escape backslashes that JSON would otherwise read as invalid escapes.

    Models writing file content (regexes, Windows paths, nested newlines)
    into a JSON string sometimes emit a single backslash where JSON
    requires two: "\\\\d" instead of "\\\\\\\\d". json.loads rejects that
    with "Invalid \\escape". Rewriting those backslashes as literal
    backslashes preserves the content the model intended.
    """
    out = []
    i = 0
    length = len(text)

    while i < length:
        ch = text[i]

        if ch != "\\":
            out.append(ch)
            i += 1
            continue

        if i + 1 >= length:
            out.append("\\\\")
            i += 1
            continue

        nxt = text[i + 1]

        if nxt == "u":
            hex_digits = text[i + 2:i + 6]
            if len(hex_digits) == 4 and all(
                c in "0123456789abcdefABCDEF" for c in hex_digits
            ):
                out.append(text[i:i + 6])
                i += 6
            else:
                out.append("\\\\")
                i += 1
            continue

        if nxt in _VALID_JSON_ESCAPES:
            out.append(text[i:i + 2])
            i += 2
            continue

        out.append("\\\\")
        i += 1

    return "".join(out)


def _safe_parse_json(text: str) -> Dict[str, Any]:
    if text is None:
        raise ValueError("Gateway returned an empty message body")

    text = _strip_code_fence(text.strip())

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        repaired = _repair_json_escapes(text)
        if repaired != text:
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass
        raise ValueError(
            f"Gateway returned malformed JSON ({e}). "
            f"Response head: {text[:300]}"
        ) from e


def _request_gateway(body: Dict[str, Any], session_id: Optional[str] = None) -> str:
    headers = {
        "Authorization": f"Bearer {AI_GATEWAY_API_KEY}",
        "Content-Type": "application/json"
    }

    if session_id:
        headers[SESSION_HEADER] = session_id

    url = f"{AI_GATEWAY_BASE_URL.rstrip('/')}{GATEWAY_CHAT_PATH}"

    response = requests.post(
        url,
        headers=headers,
        json=body,
        timeout=TIMEOUT
    )

    if response.status_code >= 400:
        raise GatewayHttpError(
            f"Gateway returned HTTP {response.status_code}: "
            f"{response.text[:300]}",
            status_code=response.status_code
        )

    try:
        data = response.json()
        choice = data["choices"][0]
        content = choice["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise ValueError(
            f"Gateway returned unexpected response: {response.text[:300]}"
        ) from e

    if content is None:
        finish_reason = choice.get("finish_reason", "unknown")
        raise ValueError(
            f"Gateway returned no message content (finish_reason={finish_reason}). "
            f"Response: {response.text[:300]}"
        )

    if choice.get("finish_reason") == "length":
        raise ValueError(
            f"Gateway response was truncated at max_tokens={AI_GATEWAY_MAX_TOKENS}. "
            f"Response head: {content[:300]}"
        )

    return content


def _call_with_retry(
    body: Dict[str, Any],
    parse_fn: Callable[[str], Any],
    session_id: Optional[str] = None
) -> Any:
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            content = _request_gateway(body, session_id)
            return parse_fn(content)
        except GatewayHttpError as e:
            if (
                e.status_code < 500
                and e.status_code != 429
                and e.status_code != 403
            ):
                raise
            last_error = e
        except Exception as e:
            last_error = e

        sleep_time = BACKOFF_BASE * (2 ** attempt) + random.uniform(0, 0.25)
        time.sleep(sleep_time)

    raise RuntimeError(
        f"ai-gateway failed after {MAX_RETRIES} retries: {str(last_error)}"
    )


# ----------------------------------
# PUBLIC API
# ----------------------------------
def parse_instruction(
    instruction: str,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    body = {
        "model": _resolve_model(),
        "messages": [
            {"role": "system", "content": PARSE_SYSTEM_PROMPT},
            {"role": "user", "content": instruction}
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": AI_GATEWAY_MAX_TOKENS
    }

    return _call_with_retry(body, _safe_parse_json, session_id)


def chat(
    messages: List[Dict[str, str]],
    system: str = CHAT_SYSTEM_PROMPT,
    model: Optional[str] = None,
    session_id: Optional[str] = None
) -> str:
    full_messages = [{"role": "system", "content": system}] + list(messages)

    body = {
        "model": model or _resolve_model(),
        "messages": full_messages,
        "max_tokens": AI_GATEWAY_MAX_TOKENS
    }

    return _call_with_retry(body, lambda s: s.strip(), session_id)


def plan_changes(
    instruction: str,
    repo_context: Dict[str, Any],
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    user_content = (
        f"Instruction: {instruction}\n\n"
        f"Repo context: {json.dumps(repo_context)}"
    )

    body = {
        "model": _resolve_model(),
        "messages": [
            {"role": "system", "content": PLAN_CHANGES_SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": AI_GATEWAY_MAX_TOKENS,
        "reasoning_effort": "none"
    }

    return _call_with_retry(body, _safe_parse_json, session_id)
