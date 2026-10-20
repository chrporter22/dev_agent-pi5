# core/llm/app.py
# --------------------------
# THIN FLASK PROXY → EXTERNAL LITELLM GATEWAY
# --------------------------
# Preserves the existing `POST /parse` contract for `core/bot`. Sends an
# OpenAI-compatible chat-completion request to the LiteLLM gateway with
# `response_format: {"type": "json_object"}` and returns strict JSON.
# Validation is hand-written per repo convention (no zod).

import json
import logging
import time

import requests
from flask import Flask, jsonify, request

import config


# --------------------------
# LOGGING
# --------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("openclaw.llm")


app = Flask(__name__)


# --------------------------
# SYSTEM PROMPT (PRESERVED FROM PRIOR LOCAL MODEL)
# --------------------------
SYSTEM_PROMPT = """You are a strict JSON API.
Return ONLY valid JSON.
No markdown.
No explanations.

Schema:
{
  "type": string,
  "language": string,
  "features": string[],
  "tests": boolean,
  "description": string
}
"""


# --------------------------
# UPSTREAM CALL
# --------------------------
def _call_gateway(instruction: str) -> dict:
    """
    Sends the user's instruction to the LiteLLM gateway and returns the parsed
    JSON content. Retries on transient errors only. Maps timeouts / HTTP errors
    to caller-friendly exceptions.
    """
    url = f"{config.AI_GATEWAY_BASE_URL}{config.LLM_GATEWAY_CHAT_PATH}"
    headers = {
        "Authorization": f"Bearer {config.AI_GATEWAY_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "model": config.AI_GATEWAY_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": instruction},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    last_err = None
    for attempt in range(1, config.LLM_MAX_RETRIES + 2):
        try:
            resp = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=config.LLM_TIMEOUT_SECONDS,
            )
            if resp.status_code >= 500:
                raise requests.HTTPError(
                    f"upstream {resp.status_code}: {resp.text[:200]}"
                )
            resp.raise_for_status()
            data = resp.json()

            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            if not content:
                raise ValueError("upstream returned empty content")

            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise ValueError("upstream JSON is not an object")
            return parsed

        except (requests.Timeout, requests.ConnectionError, requests.HTTPError, ValueError) as e:
            last_err = e
            log.warning(
                "gateway call failed (attempt %s/%s): %s",
                attempt,
                config.LLM_MAX_RETRIES + 1,
                e,
            )
            if attempt <= config.LLM_MAX_RETRIES:
                time.sleep(min(2 ** attempt, 8))

    raise RuntimeError(f"gateway unreachable: {last_err}")


# --------------------------
# STRICT PARSE ENDPOINT (CONTRACT PRESERVED FOR core/bot)
# --------------------------
@app.route("/parse", methods=["POST"])
def parse():
    data = request.get_json(silent=True)

    if not isinstance(data, dict) or "instruction" not in data:
        return jsonify({"error": "Missing instruction"}), 400

    instruction = data["instruction"]
    if not isinstance(instruction, str) or not instruction.strip():
        return jsonify({"error": "instruction must be a non-empty string"}), 400

    try:
        parsed = _call_gateway(instruction)
    except requests.Timeout:
        return jsonify({"error": "gateway timeout"}), 504
    except requests.HTTPError as e:
        return jsonify({"error": "gateway HTTP error", "detail": str(e)}), 502
    except (ValueError, RuntimeError) as e:
        return jsonify({"error": "gateway parse failure", "detail": str(e)}), 502

    return jsonify(parsed), 200


# --------------------------
# HEALTH
# --------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# --------------------------
# ENTRYPOINT (LOCAL DEV ONLY — PROD USES GUNICORN)
# --------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.LLM_PORT)
