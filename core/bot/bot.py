import json
import time
import uuid

import redis
import requests

from config import (
    AI_GATEWAY_ALLOWED_MODELS,
    ALLOWED_USER,
    DEFAULT_REPO,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
    REDIS_USER,
    TELEGRAM_TOKEN
)

from chat_store import ChatStore
from github_client import get_pr, list_prs, merge_pr
from rate_limiter import RateLimiter
from telegram_sender import _chunk_send

# ============================================================================
# TELEGRAM BOT — core/bot/bot.py
# Polls Telegram, gates commands to ALLOWED_USER, queues build + chat jobs,
# and serves synchronous /pr / /status / /jobs / /job lookups.
# ============================================================================

BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    username=REDIS_USER,
    password=REDIS_PASSWORD,
    decode_responses=True
)

rate_limiter = RateLimiter(redis_client)
chat_store = ChatStore()
offset = None


# ---------------------------
# TELEGRAM HELPERS
# ---------------------------
def send_message(chat_id, text):
    requests.post(
        f"{BASE}/sendMessage",
        json={"chat_id": chat_id, "text": text}
    )


# ---------------------------
# HELP TEXT
# ---------------------------
HELP_TEXT = (
    "Available Commands:\n\n"
    "/build [owner/repo] <feature>  — queue a build, open a PR\n"
    "/chat <text>                    — dictation to the AI gateway\n"
    "/clear                          — wipe chat history\n"
    "/model <name>                   — set per-chat model override for /chat\n"
    "/pr list                        — list open PRs for DEFAULT_REPO\n"
    "/pr <url|num>                   — show PR details\n"
    "/pr approve <url|num>           — merge a PR\n"
    "/jobs                           — list recent jobs\n"
    "/job <id>                       — show job status\n"
    "/status                         — queue + worker status"
)

PR_HELP = (
    "PR commands:\n\n"
    "/pr list\n"
    "/pr <url|num>\n"
    "/pr approve <url|num>"
)


# ---------------------------
# SYSTEM STATUS
# ---------------------------
def get_system_status():
    try:
        queued = redis_client.llen("queue:jobs")
        processing = redis_client.llen("queue:processing")
        dead = redis_client.llen("queue:dead")
        heartbeat = redis_client.get("worker:heartbeat")

        msg = (
            "System Status\n\n"
            "Redis: online\n"
            f"Queued Jobs: {queued}\n"
            f"Processing Jobs: {processing}\n"
            f"Dead Letter Jobs: {dead}"
        )

        if heartbeat:
            msg += f"\nWorker Heartbeat: {heartbeat}"

        return msg
    except Exception as e:
        return f"Status check failed:\n{str(e)}"


# ---------------------------
# JOB STATUS
# ---------------------------
def get_job_status(job_id):
    data = redis_client.hgetall(f"job:{job_id}")

    if not data:
        return "Job not found."

    msg = (
        f"Job {job_id}\n"
        f"Type: {data.get('type', 'build')}\n"
        f"Status: {data.get('status')}\n"
    )

    if data.get("repo"):
        msg += f"Repo: {data.get('repo')}\n"

    description = data.get("feature") or data.get("text")
    if description:
        msg += f"Description: {description}\n"

    msg += f"Retries: {data.get('retries')}\n"
    msg += f"Updated: {data.get('updated_at', 'unknown')}"

    result = data.get("result")
    if result:
        msg += f"\n\nResult:\n{result[:1500]}"

    pr_url = data.get("pr_url")
    if pr_url:
        msg += f"\n\nPR: {pr_url}"

    return msg


# ---------------------------
# RECENT JOBS
# ---------------------------
def list_jobs():
    job_ids = redis_client.zrevrange("jobs:index", 0, 10)

    if not job_ids:
        return "No jobs found."

    message = "Jobs:\n"

    for job_id in job_ids:
        h = redis_client.hgetall(f"job:{job_id}")
        status = h.get("status", "?")
        job_type = h.get("type", "build")
        description = h.get("feature") or h.get("text") or "(no description)"

        message += (
            f"\n• {job_id[:8]}"
            f" | {job_type}"
            f" | {status}"
            f" | {description}"
        )

    return message


# ---------------------------
# BUILD JOB
# ---------------------------
def queue_build(chat_id, repo, feature):
    job_id = str(uuid.uuid4())
    created_at = int(time.time())

    if redis_client.exists(f"job:{job_id}"):
        send_message(chat_id, "Duplicate job ignored.")
        return

    job_data = {
        "id": job_id,
        "type": "build",
        "chat_id": chat_id,
        "repo": repo,
        "feature": feature,
        "instruction": feature,
        "created_at": created_at,
        "retries": 0,
        "status": "queued"
    }

    redis_client.rpush("queue:jobs", json.dumps(job_data))

    redis_client.hset(
        f"job:{job_id}",
        mapping={
            "status": "queued",
            "type": "build",
            "feature": feature,
            "created_at": created_at,
            "retries": 0
        }
    )

    redis_client.zadd("jobs:index", {job_id: created_at})

    target = repo or DEFAULT_REPO or "(no repo)"
    send_message(
        chat_id,
        f"Job queued:\n{job_id}\nRepo: {target}\nFeature: {feature}"
    )


# ---------------------------
# CHAT JOB
# ---------------------------
def queue_chat(chat_id, text):
    job_id = str(uuid.uuid4())
    created_at = int(time.time())

    if redis_client.exists(f"job:{job_id}"):
        send_message(chat_id, "Duplicate job ignored.")
        return

    job_data = {
        "id": job_id,
        "type": "chat",
        "chat_id": chat_id,
        "text": text,
        "created_at": created_at,
        "retries": 0,
        "status": "queued"
    }

    redis_client.rpush("queue:jobs", json.dumps(job_data))

    redis_client.hset(
        f"job:{job_id}",
        mapping={
            "status": "queued",
            "type": "chat",
            "text": text,
            "created_at": created_at,
            "retries": 0
        }
    )

    redis_client.zadd("jobs:index", {job_id: created_at})

    send_message(chat_id, f"Chat queued:\n{job_id}")


# ---------------------------
# PR COMMANDS
# ---------------------------
def _pr_repo():
    if not DEFAULT_REPO:
        return None
    return DEFAULT_REPO


def handle_pr_command(chat_id, text):
    parts = text.split()

    if len(parts) == 1:
        send_message(chat_id, PR_HELP)
        return

    subcommand = parts[1]
    repo = _pr_repo()

    if not repo:
        send_message(chat_id, "DEFAULT_REPO not set in .env")
        return

    if subcommand == "list":
        try:
            prs = list_prs(repo)
        except Exception as e:
            send_message(chat_id, f"Failed to list PRs:\n{e}")
            return

        if not prs:
            send_message(chat_id, f"No open PRs for {repo}.")
            return

        lines = [f"Open PRs for {repo}:\n"]
        for pr in prs[:10]:
            lines.append(f"#{pr['number']} {pr['title']}")
            lines.append(f"  {pr['html_url']}")

        _chunk_send(chat_id, "\n".join(lines))
        return

    if subcommand == "approve":
        if len(parts) < 3:
            send_message(chat_id, "Usage: /pr approve <url|num>")
            return

        identifier = parts[2]

        try:
            result = merge_pr(repo, identifier)
        except Exception as e:
            send_message(chat_id, f"Failed to merge PR:\n{e}")
            return

        if result.get("merged"):
            sha = (result.get("sha") or "")[:8]
            send_message(chat_id, f"PR merged ({sha})")
        else:
            send_message(
                chat_id,
                result.get("message", "Merge did not complete.")
            )
        return

    identifier = subcommand

    try:
        pr = get_pr(repo, identifier)
    except Exception as e:
        send_message(chat_id, f"Failed to get PR:\n{e}")
        return

    body = pr.get("body") or ""
    msg = (
        f"#{pr['number']} {pr['title']}\n"
        f"State: {pr['state']}\n"
        f"Branch: {pr['head']['ref']} → {pr['base']['ref']}\n"
        f"Author: {pr['user']['login']}\n"
        f"URL: {pr['html_url']}\n"
        f"\n{body[:1500]}"
    )
    _chunk_send(chat_id, msg)


# ---------------------------
# COMMAND HANDLER
# ---------------------------
def handle_message(msg):
    user_id = msg["from"]["id"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()

    if user_id != ALLOWED_USER:
        return

    if not rate_limiter.check(user_id):
        send_message(chat_id, "Rate limit exceeded.")
        return

    # ==================================================
    # /build [owner/repo] <feature>
    # ==================================================
    if text.startswith("/build"):
        parts = text.split(" ", 2)

        if len(parts) < 2:
            send_message(chat_id, "Usage: /build [owner/repo] <feature>")
            return

        if len(parts) == 2:
            queue_build(chat_id, None, parts[1].strip())
        elif len(parts) >= 3 and "/" in parts[1]:
            queue_build(chat_id, parts[1].strip(), parts[2].strip())
        else:
            send_message(chat_id, "Usage: /build [owner/repo] <feature>")
        return

    # ==================================================
    # /chat <text>
    # ==================================================
    if text.startswith("/chat"):
        chat_text = text[len("/chat"):].strip()

        if not chat_text:
            send_message(chat_id, "Usage: /chat <text>")
            return

        queue_chat(chat_id, chat_text)
        return

    # ==================================================
    # /clear
    # ==================================================
    if text == "/clear":
        chat_store.clear(chat_id)
        send_message(chat_id, "Chat history cleared.")
        return

    # ==================================================
    # /model <name>
    # ==================================================
    if text.startswith("/model"):
        model = text[len("/model"):].strip()

        if not model:
            send_message(chat_id, "Usage: /model <name>")
            return

        if model not in AI_GATEWAY_ALLOWED_MODELS:
            send_message(
                chat_id,
                f"Unknown model: {model}\n"
                f"Allowed: {', '.join(AI_GATEWAY_ALLOWED_MODELS)}"
            )
            return

        chat_store.set_model(chat_id, model)
        send_message(chat_id, f"Model set to: {model}")
        return

    # ==================================================
    # /pr ...
    # ==================================================
    if text.startswith("/pr"):
        handle_pr_command(chat_id, text)
        return

    # ==================================================
    # /jobs
    # ==================================================
    if text == "/jobs":
        send_message(chat_id, list_jobs())
        return

    # ==================================================
    # /job <id>
    # ==================================================
    if text.startswith("/job"):
        parts = text.split(" ", 1)

        if len(parts) < 2:
            send_message(chat_id, "Usage: /job <job_id>")
            return

        job_id = parts[1].strip()
        send_message(chat_id, get_job_status(job_id))
        return

    # ==================================================
    # /status
    # ==================================================
    if text == "/status":
        send_message(chat_id, get_system_status())
        return

    # ==================================================
    # UNKNOWN
    # ==================================================
    send_message(chat_id, HELP_TEXT)


# ---------------------------
# TELEGRAM POLLING LOOP
# ---------------------------
def poll():
    global offset

    while True:
        try:
            res = requests.get(
                f"{BASE}/getUpdates",
                params={"timeout": 30, "offset": offset}
            ).json()

            for update in res.get("result", []):
                offset = update["update_id"] + 1

                if "message" in update:
                    handle_message(update["message"])

        except Exception as e:
            print(f"Polling error: {e}")

        time.sleep(1)


if __name__ == "__main__":
    poll()
