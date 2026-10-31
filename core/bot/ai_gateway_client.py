import json
import random
import time
from typing import Any, Callable, Dict, List

import requests

from config import AI_GATEWAY_API_KEY, AI_GATEWAY_BASE_URL, AI_GATEWAY_MODEL

# ============================================================================
# AI GATEWAY CLIENT — core/bot/ai_gateway_client.py
# Thin HTTP client for the external ~/ai-gateway LiteLLM endpoint.
# Public API: parse_instruction, chat, plan_changes.
# ============================================================================

# ----------------------------------
# CONFIG
# ----------------------------------
TIMEOUT = 30
MAX_RETRIES = 3
BACKOFF_BASE = 0.5

GATEWAY_CHAT_PATH = "/v1/chat/completions"


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
    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else ""

    return json.loads(text)


def _request_gateway(body: Dict[str, Any]) -> str:
    headers = {
        "Authorization": f"Bearer {AI_GATEWAY_API_KEY}",
        "Content-Type": "application/json"
    }

    url = f"{AI_GATEWAY_BASE_URL.rstrip('/')}{GATEWAY_CHAT_PATH}"

    response = requests.post(
        url,
        headers=headers,
        json=body,
        timeout=TIMEOUT
    )

    response.raise_for_status()

    try:
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as e:
        raise ValueError(
            f"Gateway returned unexpected response: {response.text[:300]}"
        ) from e


def _call_with_retry(body: Dict[str, Any], parse_fn: Callable[[str], Any]) -> Any:
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            content = _request_gateway(body)
            return parse_fn(content)
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
def parse_instruction(instruction: str) -> Dict[str, Any]:
    body = {
        "model": AI_GATEWAY_MODEL,
        "messages": [
            {"role": "system", "content": PARSE_SYSTEM_PROMPT},
            {"role": "user", "content": instruction}
        ],
        "response_format": {"type": "json_object"}
    }

    return _call_with_retry(body, _safe_parse_json)


def chat(
    messages: List[Dict[str, str]],
    system: str = CHAT_SYSTEM_PROMPT,
    model: Optional[str] = None
) -> str:
    full_messages = [{"role": "system", "content": system}] + list(messages)

    body = {
        "model": model or AI_GATEWAY_MODEL,
        "messages": full_messages
    }

    return _call_with_retry(body, lambda s: s.strip())


def plan_changes(
    instruction: str,
    repo_context: Dict[str, Any]
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
        "response_format": {"type": "json_object"}
    }

    return _call_with_retry(body, _safe_parse_json)
