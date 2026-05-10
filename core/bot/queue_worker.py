import json
import time
import redis
import traceback

from llm_client import parse_instruction
from github_client import create_branch, create_pr
from config import (
    REDIS_HOST,
    REDIS_PORT,
    REDIS_PASSWORD
)

# ----------------------------------
# REDIS CLIENT
# ----------------------------------
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True
)

# ----------------------------------
# CONSTANTS
# ----------------------------------
WORKER_HEARTBEAT_KEY = "worker:heartbeat"

QUEUE_JOBS = "queue:jobs"
QUEUE_PROCESSING = "queue:processing"
QUEUE_DEAD = "queue:dead"

MAX_RETRIES = 3


# ----------------------------------
# HEARTBEAT
# ----------------------------------
def update_heartbeat():
    redis_client.set(
        WORKER_HEARTBEAT_KEY,
        int(time.time()),
        ex=30
    )


# ----------------------------------
# DEAD LETTER HANDLER
# ----------------------------------
def send_to_dead_letter(job, error):
    job_id = job.get("id")

    failed_payload = {
        "job": job,
        "error": str(error),
        "failed_at": int(time.time())
    }

    # ---------------- UPDATE JOB ----------------
    redis_client.hset(
        f"job:{job_id}",
        mapping={
            "status": "failed",
            "error": str(error),
            "updated_at": int(time.time())
        }
    )

    # ---------------- STORE DEAD LETTER ----------------
    redis_client.rpush(
        QUEUE_DEAD,
        json.dumps(failed_payload)
    )

    # ---------------- INDEX FAILED JOB ----------------
    redis_client.zadd(
        "jobs:failed",
        {job_id: int(time.time())}
    )


# ----------------------------------
# STORE PR METADATA
# ----------------------------------
def store_pull_request(job, job_id, pr_url):
    redis_client.hset(
        f"pr:{job_id}",
        mapping={
            "job_id": job_id,
            "feature": job["feature"],
            "url": pr_url,
            "created_at": int(time.time())
        }
    )

    redis_client.zadd(
        "prs:index",
        {job_id: int(time.time())}
    )


# ----------------------------------
# UPDATE JOB STATUS
# ----------------------------------
def update_job_status(job_id, status, extra=None):
    payload = {
        "status": status,
        "updated_at": int(time.time())
    }

    if extra:
        payload.update(extra)

    redis_client.hset(
        f"job:{job_id}",
        mapping=payload
    )


# ----------------------------------
# RETRY LOGIC
# ----------------------------------
def increment_retry(job):
    retries = int(job.get("retries", 0))
    retries += 1

    job["retries"] = retries

    return retries


# ----------------------------------
# MAIN WORKER LOOP
# ----------------------------------
def process_job():

    print("Worker started...")

    while True:

        job_data = None
        job = None
        job_id = None

        try:

            # ----------------------------------
            # HEARTBEAT
            # ----------------------------------
            update_heartbeat()

            # ----------------------------------
            # FETCH JOB
            # ----------------------------------
            job_data = redis_client.brpoplpush(
                QUEUE_JOBS,
                QUEUE_PROCESSING,
                timeout=5
            )

            if not job_data:
                time.sleep(1)
                continue

            # ----------------------------------
            # PARSE JOB
            # ----------------------------------
            job = json.loads(job_data)
            job_id = job["id"]

            print(f"Processing job: {job_id}")

            # ----------------------------------
            # SET RUNNING
            # ----------------------------------
            update_job_status(
                job_id,
                "running"
            )

            redis_client.zadd(
                "jobs:running",
                {job_id: int(time.time())}
            )

            # ----------------------------------
            # LLM PROCESSING
            # ----------------------------------
            parsed = parse_instruction(
                job["instruction"]
            )

            # ----------------------------------
            # GITHUB BRANCH
            # ----------------------------------
            branch = create_branch()

            # ----------------------------------
            # CREATE PR
            # ----------------------------------
            pr_url = create_pr(
                branch,
                f"[OpenClaw] {job['feature']}",
                json.dumps(parsed, indent=2)
            )

            # ----------------------------------
            # STORE PR METADATA
            # ----------------------------------
            store_pull_request(
                job,
                job_id,
                pr_url
            )

            # ----------------------------------
            # SUCCESS STATUS
            # ----------------------------------
            update_job_status(
                job_id,
                "complete",
                {
                    "result": pr_url
                }
            )

            redis_client.zadd(
                "jobs:complete",
                {job_id: int(time.time())}
            )

            # ----------------------------------
            # REMOVE PROCESSING JOB
            # ----------------------------------
            redis_client.lrem(
                QUEUE_PROCESSING,
                1,
                job_data
            )

            print(f"Job complete: {job_id}")

        except Exception as e:

            error_trace = traceback.format_exc()

            print(f"Worker error:\n{error_trace}")

            # ----------------------------------
            # SAFE FAILURE HANDLING
            # ----------------------------------
            if job and job_id:

                retries = increment_retry(job)

                update_job_status(
                    job_id,
                    "failed",
                    {
                        "error": str(e),
                        "retries": retries
                    }
                )

                # ----------------------------------
                # RETRY OR DEAD LETTER
                # ----------------------------------
                if retries < MAX_RETRIES:

                    print(
                        f"Retrying job "
                        f"{job_id} "
                        f"({retries}/{MAX_RETRIES})"
                    )

                    redis_client.rpush(
                        QUEUE_JOBS,
                        json.dumps(job)
                    )

                else:

                    print(
                        f"Job failed permanently: "
                        f"{job_id}"
                    )

                    send_to_dead_letter(
                        job,
                        str(e)
                    )

                # ----------------------------------
                # REMOVE PROCESSING ENTRY
                # ----------------------------------
                try:
                    redis_client.lrem(
                        QUEUE_PROCESSING,
                        1,
                        job_data
                    )
                except Exception:
                    pass

        time.sleep(0.2)


# ----------------------------------
# ENTRYPOINT
# ----------------------------------
if __name__ == "__main__":
    process_job()
