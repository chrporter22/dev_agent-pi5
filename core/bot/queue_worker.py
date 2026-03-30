import json
import uuid
import time
from llm_client import parse_instruction
from github_client import create_branch, create_pr

def process_job(redis_client):
    while True:
        _, job_data = redis_client.blpop("jobs:queue")
        job = json.loads(job_data)
        job_id = job["id"]

        try:
            parsed = parse_instruction(job["instruction"])
            branch = create_branch()

            body = f"""
Job ID: {job_id}
Original Instruction:
{job['instruction']}

Parsed Schema:
{json.dumps(parsed, indent=2)}
"""

            pr_url = create_pr(
                branch,
                f"[OpenClaw Task] {job['feature']}",
                body
            )

            redis_client.hset(f"jobs:status:{job_id}", mapping={
                "status": "complete",
                "pr_url": pr_url
            })

        except Exception as e:
            redis_client.hset(f"jobs:status:{job_id}", mapping={
                "status": "failed",
                "error": str(e)
            })

        time.sleep(1)
