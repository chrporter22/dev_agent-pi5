import requests
import uuid
from config import GITHUB_TOKEN, SANDBOX_REPO

BASE = "https://api.github.com"

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

def create_branch(base="main"):
    branch = f"feature/{uuid.uuid4()}"
    ref = requests.get(
        f"{BASE}/repos/{SANDBOX_REPO}/git/ref/heads/{base}",
        headers=HEADERS
    ).json()

    sha = ref["object"]["sha"]

    requests.post(
        f"{BASE}/repos/{SANDBOX_REPO}/git/refs",
        headers=HEADERS,
        json={
            "ref": f"refs/heads/{branch}",
            "sha": sha
        }
    )

    return branch

def create_pr(branch, title, body):
    response = requests.post(
        f"{BASE}/repos/{SANDBOX_REPO}/pulls",
        headers=HEADERS,
        json={
            "title": title,
            "head": branch,
            "base": "main",
            "body": body
        }
    )
    return response.json()["html_url"]
