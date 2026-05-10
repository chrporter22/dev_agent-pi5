import requests
import redis
import json
import uuid
import time

from config import (
    TELEGRAM_TOKEN,
    ALLOWED_USER,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_PASSWORD
)

from rate_limiter import RateLimiter
from github_client import approve_pr

BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    decode_responses=True
)

rate_limiter = RateLimiter(redis_client)
offset = None


# ---------------------------
# TELEGRAM HELPERS
# ---------------------------
def send_message(chat_id, text):
    requests.post(
        f"{BASE}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text
        }
    )


# ---------------------------
# SYSTEM STATUS
# ---------------------------
def get_system_status():
    try:
        queued = redis_client.llen("queue:jobs")
        processing = redis_client.llen("queue:processing")
        dead = redis_client.llen("queue:dead")

        return (
            "System Status\n\n"
            f"Redis: online\n"
            f"Queued Jobs: {queued}\n"
            f"Processing Jobs: {processing}\n"
            f"Dead Letter Jobs: {dead}"
        )

    except Exception as e:
        return f"Status check failed:\n{str(e)}"


# ---------------------------
# LIST PULL REQUESTS
# ---------------------------
def list_pull_requests():
    prs = redis_client.zrevrange("prs:index", 0, 10)

    if not prs:
        return "No pull requests found."

    message = "Recent Pull Requests:\n"

    for pr_id in prs:
        pr = redis_client.hgetall(f"pr:{pr_id}")

        message += (
            f"\n• {pr_id[:8]}"
            f"\nFeature: {pr.get('feature', 'unknown')}"
            f"\nURL: {pr.get('url', 'missing')}\n"
        )

    return message


# ---------------------------
# APPROVE PULL REQUEST
# ---------------------------
def approve_pull_request(pr_number):
    try:
        approve_pr(pr_number)

        return f"Approved PR #{pr_number}"

    except Exception as e:
        return f"Approval failed:\n{str(e)}"


# ---------------------------
# JOB STATUS
# ---------------------------
def get_job_status(job_id):
    data = redis_client.hgetall(f"job:{job_id}")

    if not data:
        return "Job not found."

    return (
        f"Job {job_id}\n"
        f"Status: {data.get('status')}\n"
        f"Feature: {data.get('feature')}\n"
        f"Retries: {data.get('retries')}\n"
        f"Updated: {data.get('updated_at', 'unknown')}"
    )


# ---------------------------
# RECENT JOBS
# ---------------------------
def list_jobs():
    job_ids = redis_client.zrevrange("jobs:index", 0, 10)

    if not job_ids:
        return "No jobs found."

    message = "Jobs:\n"

    for job_id in job_ids:
        status = redis_client.hget(f"job:{job_id}", "status")
        feature = redis_client.hget(f"job:{job_id}", "feature")

        message += (
            f"\n• {job_id[:8]}"
            f" | {status}"
            f" | {feature}"
        )

    return message


# ---------------------------
# BUILD JOB
# ---------------------------
def queue_build(chat_id, feature):
    job_id = str(uuid.uuid4())
    created_at = int(time.time())

    # ---------------- DEDUP SAFETY ----------------
    if redis_client.exists(f"job:{job_id}"):
        send_message(chat_id, "Duplicate job ignored.")
        return

    job_data = {
        "id": job_id,
        "feature": feature,
        "instruction": feature,
        "created_at": created_at,
        "retries": 0,
        "status": "queued"
    }

    # ---------------- QUEUE JOB ----------------
    redis_client.rpush(
        "queue:jobs",
        json.dumps(job_data)
    )

    # ---------------- JOB STATE ----------------
    redis_client.hset(
        f"job:{job_id}",
        mapping={
            "status": "queued",
            "feature": feature,
            "created_at": created_at,
            "retries": 0
        }
    )

    # ---------------- INDEX ----------------
    redis_client.zadd(
        "jobs:index",
        {job_id: created_at}
    )

    send_message(
        chat_id,
        f"Job queued:\n{job_id}"
    )


# ---------------------------
# COMMAND HANDLER
# ---------------------------
def handle_message(msg):
    user_id = msg["from"]["id"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()

    # ---------------- AUTH ----------------
    if user_id != ALLOWED_USER:
        return

    # ---------------- RATE LIMIT ----------------
    if not rate_limiter.check(user_id):
        send_message(chat_id, "Rate limit exceeded.")
        return

    # ==================================================
    # /build <feature>
    # ==================================================
    if text.startswith("/build"):

        parts = text.split(" ", 1)

        if len(parts) < 2:
            send_message(
                chat_id,
                "Usage: /build <feature>"
            )
            return

        feature = parts[1].strip()

        queue_build(chat_id, feature)

    # ==================================================
    # /jobs
    # ==================================================
    elif text.startswith("/jobs"):

        send_message(
            chat_id,
            list_jobs()
        )

    # ==================================================
    # /job <id>
    # ==================================================
    elif text.startswith("/job"):

        parts = text.split(" ", 1)

        if len(parts) < 2:
            send_message(
                chat_id,
                "Usage: /job <job_id>"
            )
            return

        job_id = parts[1].strip()

        send_message(
            chat_id,
            get_job_status(job_id)
        )

    # ==================================================
    # /status
    # ==================================================
    elif text.startswith("/status"):

        send_message(
            chat_id,
            get_system_status()
        )

    # ==================================================
    # /listpr
    # ==================================================
    elif text.startswith("/listpr"):

        send_message(
            chat_id,
            list_pull_requests()
        )

    # ==================================================
    # /approvepr <pr_number>
    # ==================================================
    elif text.startswith("/approvepr"):

        parts = text.split(" ", 1)

        if len(parts) < 2:
            send_message(
                chat_id,
                "Usage: /approvepr <pr_number>"
            )
            return

        pr_number = parts[1].strip()

        send_message(
            chat_id,
            approve_pull_request(pr_number)
        )

    # ==================================================
    # UNKNOWN COMMAND
    # ==================================================
    else:

        send_message(
            chat_id,
            (
                "Available Commands:\n\n"
                "/build <feature>\n"
                "/jobs\n"
                "/job <id>\n"
                "/status\n"
                "/listpr\n"
                "/approvepr <pr_number>"
            )
        )


# ---------------------------
# TELEGRAM POLLING LOOP
# ---------------------------
def poll():
    global offset

    while True:

        try:

            res = requests.get(
                f"{BASE}/getUpdates",
                params={
                    "timeout": 30,
                    "offset": offset
                }
            ).json()

            for update in res.get("result", []):

                offset = update["update_id"] + 1

                if "message" in update:
                    handle_message(update["message"])

        except Exception as e:
            print(f"Polling error: {e}")

        time.sleep(1)


# ---------------------------
# ENTRYPOINT
# ---------------------------
if __name__ == "__main__":
    poll()
