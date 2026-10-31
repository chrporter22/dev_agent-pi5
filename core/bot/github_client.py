import os
import subprocess
import time
from typing import Any, Dict, List, Optional

import requests

from config import GITHUB_TOKEN

# ============================================================================
# GITHUB CLIENT — core/bot/github_client.py
# Git CLI wrapper + GitHub REST client for clone/branch/commit/push/PR.
# Public API: clone_or_pull, create_branch, commit_all, push, open_pr,
#             list_prs, get_pr, merge_pr.
# ============================================================================

GITHUB_API_BASE = "https://api.github.com"


# ----------------------------------
# GIT CLI HELPERS
# ----------------------------------
def _run_git(args: List[str], cwd: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {result.stderr.strip()}"
        )

    return result.stdout.strip()


def clone_or_pull(repo: str, sandbox_dir: str, base_branch: str = "main") -> None:
    if os.path.isdir(os.path.join(sandbox_dir, ".git")):
        _run_git(["checkout", base_branch], sandbox_dir)
        _run_git(["pull", "--ff-only", "origin", base_branch], sandbox_dir)
        return

    clone_url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{repo}.git"
    parent = os.path.dirname(sandbox_dir) or "."
    _run_git(["clone", clone_url, sandbox_dir], parent)
    _run_git(["checkout", base_branch], sandbox_dir)


def create_branch(
    sandbox_dir: str,
    branch_name: str,
    base_branch: str = "main"
) -> None:
    _run_git(["fetch", "origin", base_branch], sandbox_dir)
    _run_git(
        ["checkout", "-B", branch_name, f"origin/{base_branch}"],
        sandbox_dir
    )


def commit_all(sandbox_dir: str, message: str) -> bool:
    _run_git(["add", "-A"], sandbox_dir)

    status = _run_git(["status", "--porcelain"], sandbox_dir)
    if not status:
        return False

    _run_git(
        [
            "-c", "user.name=openclaw-bot",
            "-c", "user.email=bot@openclaw.local",
            "commit", "-m", message
        ],
        sandbox_dir
    )
    return True


def push(sandbox_dir: str, branch_name: str) -> None:
    _run_git(["push", "origin", branch_name], sandbox_dir)


# ----------------------------------
# GITHUB REST HELPERS
# ----------------------------------
def _auth_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }


def _rest_call(method: str, url: str, **kwargs) -> requests.Response:
    headers = kwargs.pop("headers", {})
    headers.update(_auth_headers())
    last_error: Optional[Exception] = None

    for attempt in range(3):
        try:
            resp = requests.request(
                method,
                url,
                headers=headers,
                timeout=30,
                **kwargs
            )

            if resp.status_code < 400 or resp.status_code == 429:
                return resp

            last_error = RuntimeError(
                f"GitHub API {resp.status_code}: {resp.text[:200]}"
            )
        except requests.RequestException as e:
            last_error = e

        time.sleep(0.5 * (2 ** attempt))

    raise last_error  # type: ignore[misc]


def _normalize_pr_id(identifier) -> int:
    if isinstance(identifier, int):
        return identifier

    s = str(identifier).strip().rstrip("/")
    if "/" in s:
        return int(s.split("/")[-1])
    return int(s)


# ----------------------------------
# PUBLIC REST API
# ----------------------------------
def open_pr(
    repo: str,
    head: str,
    base: str,
    title: str,
    body: str
) -> Dict[str, Any]:
    url = f"{GITHUB_API_BASE}/repos/{repo}/pulls"
    resp = _rest_call(
        "POST",
        url,
        json={"head": head, "base": base, "title": title, "body": body}
    )
    resp.raise_for_status()
    return resp.json()


def list_prs(
    repo: str,
    state: str = "open",
    per_page: int = 10
) -> List[Dict[str, Any]]:
    url = f"{GITHUB_API_BASE}/repos/{repo}/pulls"
    resp = _rest_call(
        "GET",
        url,
        params={"state": state, "per_page": per_page}
    )
    resp.raise_for_status()
    return resp.json()


def get_pr(repo: str, identifier) -> Dict[str, Any]:
    number = _normalize_pr_id(identifier)
    url = f"{GITHUB_API_BASE}/repos/{repo}/pulls/{number}"
    resp = _rest_call("GET", url)
    resp.raise_for_status()
    return resp.json()


def merge_pr(
    repo: str,
    identifier,
    commit_title: Optional[str] = None,
    commit_message: Optional[str] = None,
    merge_method: str = "merge"
) -> Dict[str, Any]:
    number = _normalize_pr_id(identifier)
    url = f"{GITHUB_API_BASE}/repos/{repo}/pulls/{number}/merge"

    payload: Dict[str, Any] = {"merge_method": merge_method}
    if commit_title:
        payload["commit_title"] = commit_title
    if commit_message:
        payload["commit_message"] = commit_message

    resp = _rest_call("PUT", url, json=payload)

    if resp.status_code == 405:
        return {
            "merged": False,
            "message": (
                "Merge blocked (branch protection, required checks, "
                "or token missing merge scope)"
            )
        }

    resp.raise_for_status()
    return resp.json()
