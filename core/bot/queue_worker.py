import json
import time
import redis
from llm_client import parse_instruction
from github_client import create_branch, create_pr
from config import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True
)


# ---------------------------
# DEAD LETTER HANDLER
# ---------------------------
def send_to_dead_letter(job, error):
    job_id = job.get("id")

    redis_client.hset(f"job:{job_id}", mapping={
        "status": "failed",
        "error": str(error),
        "updated_at": int(time.time())
    })

    redis_client.rpush("queue:dead", json.dumps({
        "job": job,
        "error": str(error),
        "failed_at": int(time.time())
    }))


# ---------------------------
# MAIN WORKER LOOP
# ---------------------------
def process_job():
    while True:
        job_data = None
        job = None
        job_id = None

        try:
            # ---------------- FETCH JOB ----------------
            job_data = redis_client.brpoplpush(
                "queue:jobs",
                "queue:processing",
                timeout=5
            )

            if not job_data:
                continue

            job = json.loads(job_data)
            job_id = job["id"]

            # ---------------- SET RUNNING ----------------
            redis_client.hset(f"job:{job_id}", "status", "running")

            # ---------------- PROCESS ----------------
            parsed = parse_instruction(job["instruction"])
            branch = create_branch()

            pr_url = create_pr(
                branch,
                f"[OpenClaw] {job['feature']}",
                json.dumps(parsed, indent=2)
            )

            # ---------------- SUCCESS ----------------
            redis_client.hset(f"job:{job_id}", mapping={
                "status": "complete",
                "result": pr_url,
                "updated_at": int(time.time())
            })

            # remove from processing queue
            redis_client.lrem("queue:processing", 1, job_data)


        except Exception as e:

            # ---------------- SAFE FAILURE HANDLING ----------------
            if job and job_id:

                redis_client.hset(f"job:{job_id}", mapping={
                    "status": "failed",
                    "error": str(e),
                    "updated_at": int(time.time())
                })

                send_to_dead_letter(job, str(e))

                try:
                    redis_client.lrem("queue:processing", 1, job_data)
                except:
                    pass

        time.sleep(0.2)


# ---------------------------
# ENTRYPOINT
# ---------------------------
if __name__ == "__main__":
    process_job()
