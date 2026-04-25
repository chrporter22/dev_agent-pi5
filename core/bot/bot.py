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
    requests.post(f"{BASE}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })


# ---------------------------
# CORE HANDLER
# ---------------------------
def handle_message(msg):
    user_id = msg["from"]["id"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    if user_id != ALLOWED_USER:
        return

    if not rate_limiter.check(user_id):
        send_message(chat_id, "Rate limit exceeded.")
        return


    # ---------------- BUILD ----------------
    if text.startswith("/build"):
        parts = text.split(" ", 1)

        if len(parts) < 2:
            send_message(chat_id, "Usage: /build <feature>")
            return

        feature = parts[1].strip()
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
        redis_client.rpush("queue:jobs", json.dumps(job_data))

        # ---------------- JOB STATE ----------------
        redis_client.hset(f"job:{job_id}", mapping={
            "status": "queued",
            "feature": feature,
            "created_at": created_at,
            "retries": 0
        })

        # ---------------- INDEX (ZSET) ----------------
        redis_client.zadd("jobs:index", {job_id: created_at})

        send_message(chat_id, f"Job queued:\n{job_id}")


    # ---------------- JOB STATUS ----------------
    elif text.startswith("/jobs"):
        job_ids = redis_client.zrevrange("jobs:index", 0, 10)

        if not job_ids:
            send_message(chat_id, "No jobs found.")
            return

        message = "Jobs:\n"

        for job_id in job_ids:
            status = redis_client.hget(f"job:{job_id}", "status")
            feature = redis_client.hget(f"job:{job_id}", "feature")

            message += f"\n• {job_id[:8]} | {status} | {feature}"

        send_message(chat_id, message)


    # ---------------- JOB DETAIL ----------------
    elif text.startswith("/job"):
        parts = text.split(" ", 1)

        if len(parts) < 2:
            send_message(chat_id, "Usage: /job <job_id>")
            return

        job_id = parts[1].strip()

        data = redis_client.hgetall(f"job:{job_id}")

        if not data:
            send_message(chat_id, "Job not found.")
            return

        send_message(chat_id,
            f"Job {job_id}\n"
            f"Status: {data.get('status')}\n"
            f"Feature: {data.get('feature')}\n"
            f"Retries: {data.get('retries')}"
        )


# ---------------------------
# TELEGRAM POLLING LOOP
# ---------------------------
def poll():
    global offset

    while True:
        res = requests.get(
            f"{BASE}/getUpdates",
            params={"timeout": 30, "offset": offset}
        ).json()

        for update in res.get("result", []):
            offset = update["update_id"] + 1

            if "message" in update:
                handle_message(update["message"])


# ---------------------------
# ENTRYPOINT
# ---------------------------
if __name__ == "__main__":
    poll()
