import json
import random
import time
from typing import Any, Callable, Dict, List, Optional

import requests

from config import (
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
SESSION_HEADER = "x-session-id"


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
    "- When adding new code, also include a .github/workflows/<name>.yml file that builds "
    "Docker images and runs unit tests.\n"
    "- Return ONLY valid JSON, no markdown, no explanation."
)


# ----------------------------------
# PRIVATE HELPERS
# ----------------------------------
def _safe_parse_json(text: str) -> Dict[str, Any]:
    if text is None:
        raise ValueError("Gateway returned an empty message body")

    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else ""

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
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
            if e.status_code < 500 and e.status_code != 429:
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
        "model": AI_GATEWAY_MODEL,
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
        "model": model or AI_GATEWAY_MODEL,
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
        "model": AI_GATEWAY_MODEL,
        "messages": [
            {"role": "system", "content": PLAN_CHANGES_SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": AI_GATEWAY_MAX_TOKENS
    }

    return _call_with_retry(body, _safe_parse_json, session_id)
