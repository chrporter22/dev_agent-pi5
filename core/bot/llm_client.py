import requests
from config import LLM_ENDPOINT

def parse_instruction(instruction: str):
    response = requests.post(
        LLM_ENDPOINT,
        json={"instruction": instruction},
        timeout=10
    )
    response.raise_for_status()
    data = response.json()

    required = ["type", "language", "features", "description"]
    if not all(field in data for field in required):
        raise ValueError("Invalid LLM schema")

    if data["language"] not in ["python", "node"]:
        raise ValueError("Unsupported language")

    return data
