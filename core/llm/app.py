from flask import Flask, request, jsonify
import requests
import json
import os

app = Flask(__name__)

# ---------------------------
# INTERNAL SERVICE ROUTING
# ---------------------------
LLAMA_SERVER_URL = os.getenv(
    "LLAMA_SERVER_URL",
    "http://openclaw-vdb:8081/completion"
)

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


# ---------------------------
# LLAMA CALL WRAPPER
# ---------------------------
def call_llama(prompt):
    payload = {
        "prompt": prompt,
        "n_predict": 256,
        "temperature": 0.2,
        "stop": ["</s>"]
    }

    response = requests.post(
        LLAMA_SERVER_URL,
        json=payload,
        timeout=30
    )

    response.raise_for_status()
    return response.json().get("content", "")


# ---------------------------
# STRICT PARSE ENDPOINT
# ---------------------------
@app.route("/parse", methods=["POST"])
def parse():
    data = request.get_json()

    if not data or "instruction" not in data:
        return jsonify({"error": "Missing instruction"}), 400

    instruction = data["instruction"]

    prompt = f"""
{SYSTEM_PROMPT}

Instruction:
{instruction}

JSON:
"""

    try:
        raw_output = call_llama(prompt)

        # Defensive JSON parsing
        cleaned = raw_output.strip()

        parsed = json.loads(cleaned)

        return jsonify(parsed)

    except json.JSONDecodeError:
        return jsonify({
            "error": "Invalid JSON from LLM",
            "raw": raw_output[:300]
        }), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------
# RAW COMPLETION PASS-THROUGH
# ---------------------------
@app.route("/completion", methods=["POST"])
def completion():
    data = request.get_json()

    if not data or "prompt" not in data:
        return jsonify({"error": "Missing prompt"}), 400

    payload = {
        "prompt": data["prompt"],
        "n_predict": data.get("n_predict", 256),
        "temperature": data.get("temperature", 0.7)
    }

    try:
        response = requests.post(
            LLAMA_SERVER_URL,
            json=payload,
            timeout=60
        )

        response.raise_for_status()
        return jsonify(response.json())

    except Exception as e:
        return jsonify({"error": "Completion failed", "detail": str(e)}), 500


# ---------------------------
# ENTRYPOINT
# ---------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
