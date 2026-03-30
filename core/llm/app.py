from flask import Flask, request, jsonify
import requests
import os
import json

app = Flask(__name__)

LLAMA_SERVER_URL = "http://127.0.0.1:8081/completion"

SYSTEM_PROMPT = """You are a strict JSON API.
Return only valid JSON.
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

def call_llama(prompt):
    payload = {
        "prompt": prompt,
        "n_predict": 256,
        "temperature": 0.2,
        "stop": ["</s>"]
    }

    response = requests.post(LLAMA_SERVER_URL, json=payload, timeout=30)
    response.raise_for_status()
    return response.json().get("content", "")

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

        # Attempt strict JSON parse
        parsed = json.loads(raw_output.strip())

        return jsonify(parsed)

    except Exception as e:
        return jsonify({"error": "LLM output invalid JSON"}), 500


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
        response = requests.post(LLAMA_SERVER_URL, json=payload, timeout=60)
        response.raise_for_status()
        return jsonify(response.json())

    except Exception:
        return jsonify({"error": "Completion failed"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
