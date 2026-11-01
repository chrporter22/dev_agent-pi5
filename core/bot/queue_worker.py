import json
import os
import time
import traceback

import redis
import requests

from ai_gateway_client import chat, plan_changes
from chat_store import ChatStore
from config import (
    DEFAULT_REPO,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
    REDIS_USER,
    SANDBOX_DIR,
    TELEGRAM_TOKEN
)

from github_client import (
    clone_or_pull,
    commit_all,
    create_branch,
    open_pr,
    push
)
from telegram_sender import _chunk_send

# ============================================================================
# QUEUE WORKER — core/bot/queue_worker.py
# Drains queue:jobs, branches on job["type"]:
#   - "build": clone → branch → plan_changes → apply → commit → push → PR
#   - "chat":  load history → chat() → append turns → reply via _chunk_send
# ============================================================================

# ----------------------------------
# REDIS CLIENT
# ----------------------------------
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    username=REDIS_USER,
    password=REDIS_PASSWORD,
    decode_responses=True
)

chat_store = ChatStore(redis_client)

# ----------------------------------
# CONSTANTS
# ----------------------------------
WORKER_HEARTBEAT_KEY = "worker:heartbeat"

QUEUE_JOBS = "queue:jobs"
QUEUE_PROCESSING = "queue:processing"
QUEUE_DEAD = "queue:dead"

MAX_RETRIES = 3

TELEGRAM_BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


# ----------------------------------
# TELEGRAM SEND
# ----------------------------------
def send_telegram(chat_id, text):
    try:
        requests.post(
            f"{TELEGRAM_BASE}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10
        )
    except Exception as e:
        print(f"Failed to send Telegram: {e}")


# ----------------------------------
# HEARTBEAT + STATUS HELPERS
# ----------------------------------
def update_heartbeat():
    redis_client.set(
        WORKER_HEARTBEAT_KEY,
        int(time.time()),
        ex=30
    )


def send_to_dead_letter(job, error):
    job_id = job.get("id")

    failed_payload = {
        "job": job,
        "error": str(error),
        "failed_at": int(time.time())
    }

    redis_client.hset(
        f"job:{job_id}",
        mapping={
            "status": "failed",
            "error": str(error),
            "updated_at": int(time.time())
        }
    )

    redis_client.rpush(QUEUE_DEAD, json.dumps(failed_payload))
    redis_client.zadd("jobs:failed", {job_id: int(time.time())})


def update_job_status(job_id, status, extra=None):
    payload = {
        "status": status,
        "updated_at": int(time.time())
    }

    if extra:
        payload.update(extra)

    redis_client.hset(f"job:{job_id}", mapping=payload)


def increment_retry(job):
    retries = int(job.get("retries", 0))
    retries += 1
    job["retries"] = retries
    return retries


# ----------------------------------
# BUILD FLOW
# ----------------------------------
def _gather_repo_context(sandbox_dir: str) -> dict:
    skip_prefixes = (
        ".git/", "node_modules/", "dist/", "build/",
        ".venv/", "venv/", "__pycache__/", ".next/"
    )
    file_list = []

    for root, _, files in os.walk(sandbox_dir):
        rel_root = os.path.relpath(root, sandbox_dir)
        if rel_root == ".":
            rel_root = ""
        if any(p in rel_root for p in (".git", "node_modules", "dist", "build")):
            continue

        for f in files:
            rel_path = f"{rel_root}/{f}" if rel_root else f
            if rel_path.startswith(skip_prefixes):
                continue
            file_list.append(rel_path)

    return {
        "files": sorted(file_list)[:200],
        "language": _detect_language(file_list)
    }


def _detect_language(file_list) -> str:
    if any(f.endswith(".py") for f in file_list):
        return "python"
    if any(f.endswith((".ts", ".tsx")) for f in file_list):
        return "typescript"
    if any(f.endswith(".js") for f in file_list):
        return "javascript"
    if any(f.endswith(".go") for f in file_list):
        return "go"
    if any(f.endswith((".java", ".kt")) for f in file_list):
        return "java"
    return "unknown"


def _apply_changes(sandbox_dir: str, files: list) -> None:
    abs_sandbox = os.path.abspath(sandbox_dir)

    for entry in files:
        path = entry.get("path", "")
        action = entry.get("action", "modify")
        content = entry.get("content", "")

        normalized = os.path.normpath(path)
        if normalized.startswith("..") or os.path.isabs(normalized):
            raise ValueError(f"Path traversal blocked: {path!r}")

        full_path = os.path.abspath(os.path.join(sandbox_dir, normalized))

        if not (full_path == abs_sandbox or full_path.startswith(abs_sandbox + os.sep)):
            raise ValueError(f"Path escapes sandbox: {path!r}")

        if action == "delete":
            if os.path.exists(full_path):
                os.remove(full_path)
        elif action in ("create", "modify"):
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as fh:
                fh.write(content)
        else:
            raise ValueError(f"Unknown action {action!r} for {path!r}")


def _format_pr_body(feature: str, files: list) -> str:
    lines = [f"**Feature:** {feature}", "", "**Files:**"]
    for entry in files:
        action = entry.get("action", "modify")
        path = entry.get("path", "?")
        lines.append(f"- `{action}` `{path}`")
    return "\n".join(lines)


def process_build_job(job: dict) -> None:
    job_id = job["id"]
    chat_id = job.get("chat_id")
    repo = job.get("repo") or DEFAULT_REPO
    feature = job["feature"]

    if not repo:
        raise RuntimeError(
            "No repo specified (use /build owner/repo <feature> "
            "or set DEFAULT_REPO in .env)"
        )

    update_job_status(job_id, "running", {"step": "clone"})
    send_telegram(chat_id, f"Job {job_id[:8]}: cloning {repo}...")
    clone_or_pull(repo, SANDBOX_DIR)

    branch_name = f"dev-agent/{job_id[:8]}"
    update_job_status(job_id, "running", {"step": "branch"})
    create_branch(SANDBOX_DIR, branch_name)

    update_job_status(job_id, "running", {"step": "plan"})
    repo_context = _gather_repo_context(SANDBOX_DIR)
    plan = plan_changes(feature, repo_context, session_id=job_id)
    files = plan.get("files", []) if isinstance(plan, dict) else []

    if not files:
        update_job_status(
            job_id,
            "complete",
            {"result": "Gateway returned no file changes."}
        )
        send_telegram(
            chat_id,
            f"Job {job_id[:8]}: gateway returned no file changes."
        )
        return

    update_job_status(job_id, "running", {"step": "apply"})
    _apply_changes(SANDBOX_DIR, files)

    update_job_status(job_id, "running", {"step": "commit"})
    committed = commit_all(
        SANDBOX_DIR,
        f"openclaw: {feature}\n\nJob {job_id[:8]}"
    )

    if not committed:
        update_job_status(
            job_id,
            "complete",
            {"result": "No changes to commit."}
        )
        send_telegram(
            chat_id,
            f"Job {job_id[:8]}: no changes to commit after apply."
        )
        return

    update_job_status(job_id, "running", {"step": "push"})
    push(SANDBOX_DIR, branch_name)

    update_job_status(job_id, "running", {"step": "pr"})
    pr = open_pr(
        repo,
        head=branch_name,
        base="main",
        title=f"openclaw: {feature[:80]}",
        body=_format_pr_body(feature, files)
    )
    pr_url = pr.get("html_url", "")

    update_job_status(
        job_id,
        "complete",
        {"pr_url": pr_url, "result": f"PR opened: {pr_url}"}
    )
    send_telegram(
        chat_id,
        f"Job {job_id[:8]} complete\nPR: {pr_url}"
    )


# ----------------------------------
# CHAT FLOW
# ----------------------------------
def process_chat_job(job: dict) -> None:
    job_id = job["id"]
    chat_id = job.get("chat_id")
    user_text = job["text"]

    if not chat_id:
        raise RuntimeError("Chat job missing chat_id")

    history = chat_store.history(chat_id)
    model_override = chat_store.get_model(chat_id)

    messages = list(history) + [{"role": "user", "content": user_text}]

    update_job_status(job_id, "running", {"step": "chat"})
    response = chat(messages, model=model_override, session_id=job_id)

    chat_store.append(chat_id, "user", user_text)
    chat_store.append(chat_id, "assistant", response)

    update_job_status(
        job_id,
        "complete",
        {"result": response[:500]}
    )

    _chunk_send(chat_id, response)


# ----------------------------------
# MAIN WORKER LOOP
# ----------------------------------
def process_job():
    print("Worker started (ai-gateway + git)...")

    while True:
        job_data = None
        job = None
        job_id = None
        chat_id = None

        try:
            update_heartbeat()

            job_data = redis_client.brpoplpush(
                QUEUE_JOBS,
                QUEUE_PROCESSING,
                timeout=5
            )

            if not job_data:
                time.sleep(1)
                continue

            job = json.loads(job_data)
            job_id = job["id"]
            chat_id = job.get("chat_id")
            job_type = job.get("type", "build")

            print(f"Processing {job_type} job: {job_id}")

            update_job_status(job_id, "running")
            redis_client.zadd("jobs:running", {job_id: int(time.time())})

            if job_type == "chat":
                process_chat_job(job)
            else:
                process_build_job(job)

            redis_client.zadd(
                "jobs:complete",
                {job_id: int(time.time())}
            )

            redis_client.lrem(QUEUE_PROCESSING, 1, job_data)
            print(f"Job complete: {job_id}")

        except Exception as e:
            error_trace = traceback.format_exc()
            print(f"Worker error:\n{error_trace}")

            if job and job_id:
                retries = increment_retry(job)

                update_job_status(
                    job_id,
                    "failed",
                    {"error": str(e), "retries": retries}
                )

                if retries < MAX_RETRIES:
                    print(
                        f"Retrying job "
                        f"{job_id} "
                        f"({retries}/{MAX_RETRIES})"
                    )
                    redis_client.rpush(QUEUE_JOBS, json.dumps(job))
                else:
                    print(f"Job failed permanently: {job_id}")
                    send_to_dead_letter(job, str(e))

                    if chat_id:
                        send_telegram(
                            chat_id,
                            (
                                f"Job {job_id[:8]} failed after "
                                f"{MAX_RETRIES} retries:\n{str(e)}"
                            )
                        )

                try:
                    redis_client.lrem(QUEUE_PROCESSING, 1, job_data)
                except Exception:
                    pass

        time.sleep(0.2)


if __name__ == "__main__":
    process_job()
