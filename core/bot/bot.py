import requests
import redis
import json
import uuid
import threading
from config import TELEGRAM_TOKEN, ALLOWED_USER, REDIS_URL
from rate_limiter import RateLimiter
from queue_worker import process_job
import os
from config import GITHUB_TOKEN, SANDBOX_REPO


GITHUB_API = "https://api.github.com"
BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

redis_client = redis.from_url(REDIS_URL)
rate_limiter = RateLimiter(redis_client)

offset = None


def github_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

def list_open_prs():
    url = f"{GITHUB_API}/repos/{SANDBOX_REPO}/pulls"
    r = requests.get(url, headers=github_headers())
    if r.status_code != 200:
        return None
    return r.json()

def approve_pr(pr_number):
    url = f"{GITHUB_API}/repos/{SANDBOX_REPO}/pulls/{pr_number}/reviews"
    r = requests.post(url, headers=github_headers(), json={
        "event": "APPROVE"
    })
    return r.status_code == 200 or r.status_code == 201

def send_message(chat_id, text):
    requests.post(f"{BASE}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })

def handle_message(msg):
    user_id = msg["from"]["id"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    if user_id != ALLOWED_USER:
        return

    if not rate_limiter.check(user_id):
        send_message(chat_id, "Rate limit exceeded. Try again later.")
        return

    # ---------------- STATUS ----------------
    if text.startswith("/status"):
        send_message(chat_id, "OpenClaw Bot running.\nZero Trust mode active.")

    # ---------------- BUILD ----------------
    elif text.startswith("/build"):
        parts = text.split(" ", 1)
        if len(parts) < 2:
            send_message(chat_id, "Usage: /build <feature_name>")
            return

        feature = parts[1].strip()
        job_id = str(uuid.uuid4())

        job = {
            "id": job_id,
            "feature": feature,
            "instruction": feature,
            "retries": 0
        }

        redis_client.rpush("jobs:queue", json.dumps(job))
        redis_client.hset(f"jobs:status:{job_id}", mapping={
            "status": "pending"
        })

        send_message(chat_id, f"Job queued:\n{job_id}")

    # ---------------- LIST PR ----------------
    elif text.startswith("/listpr"):
        prs = list_open_prs()
        if prs is None:
            send_message(chat_id, "Failed to fetch PRs.")
            return

        if not prs:
            send_message(chat_id, "No open pull requests.")
            return

        message = "Open Pull Requests:\n"
        for pr in prs:
            message += f"#{pr['number']} - {pr['title']}\n"

        send_message(chat_id, message)

    # ---------------- APPROVE PR ----------------
    elif text.startswith("/approvepr"):
        parts = text.split(" ", 1)
        if len(parts) < 2:
            send_message(chat_id, "Usage: /approvepr <PR#>")
            return

        pr_number = parts[1].strip()

        if not pr_number.isdigit():
            send_message(chat_id, "Invalid PR number.")
            return

        success = approve_pr(pr_number)

        if success:
            send_message(chat_id, f"PR #{pr_number} approved.")
        else:
            send_message(chat_id, "Failed to approve PR.")

    # ---------------- JOB STATUS ----------------
    elif text.startswith("/jobs"):
        keys = redis_client.keys("jobs:status:*")

        if not keys:
            send_message(chat_id, "No jobs found.")
            return

        message = "Job Status:\n"
        for key in keys:
            job_id = key.decode().split(":")[-1]
            status = redis_client.hget(key, "status")
            if status:
                status = status.decode()
                message += f"{job_id[:8]}... : {status}\n"

        send_message(chat_id, message)

def poll():
    global offset
    while True:
        response = requests.get(
            f"{BASE}/getUpdates",
            params={"timeout": 30, "offset": offset}
        ).json()

        for update in response.get("result", []):
            offset = update["update_id"] + 1
            if "message" in update:
                handle_message(update["message"])

if __name__ == "__main__":
    worker = threading.Thread(target=process_job, args=(redis_client,))
    worker.daemon = True
    worker.start()
    poll()
