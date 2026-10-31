---
name: no-agent-push
description: The agent never pushes to GitHub, never opens PRs, never force-pushes, and never writes remote refs. Only the human user pushes. Use whenever the work would otherwise end with `git push`, `gh pr create`, `gh repo create`, force-push, branch publish, tag push, or any remote write. Triggers: finishing a task, "commit and push", "open a PR", "publish the branch", "push to main", "create a release", `git push`, `gh pr create`, `git push --force`, `git push origin --tags`.
---

# No Agent Push

The agent does not push to GitHub. Ever. The human user is the only actor that writes to a remote.

The reason is simple and durable: the agent works on a session-by-session basis and is not the system's owner of record. The human user is. Git history is permanent, force-push destroys teammates' commits, and a misconfigured push by an agent can ship secrets, half-finished work, or destructive history rewrites in seconds. The agent's job is to make the next push safe and obvious; the user's job is to do it.

## The rule

- The agent **never** runs any command that writes to a remote: `git push` of any kind, `gh pr create`, `gh repo create`, `gh release create`, `git push --force`, `git push --force-with-lease`, `git push --mirror`, or any equivalent on other hosts.
- The agent stages and commits locally with `git add` and `git commit`. It does not push.
- The agent runs all checks (lint, type, test, build) inside Docker per `docker-testing` so the user knows the next push will be green.
- The agent hands off: at the end of a task it tells the user what to push, on what branch, and what command to run. The user runs it.

### In this repo

This repo contains a Telegram bot (`core/bot`) that **does** push to GitHub and open PRs as part of its product behavior — that is by design and outside the scope of this skill. The skill governs the **agent working in the repo**, not the bot running in production. The agent stages the code; the bot runs in a container with `GITHUB_TOKEN`; the user runs the agent's hand-off commands on their own workstation.

## What the agent does do

- `git status`, `git diff`, `git log` — read freely.
- `git add <paths>` — stage specific paths it has reviewed (never `git add -A` or `git add .` on a repo with `.ai/` active without reviewing the diff first; see `pii-redaction`).
- `git commit -m "<message>"` — local commit only. Do not pass `--amend` to a commit that has already been pushed; the user may have pulled it.
- `git fetch` and read-only remote inspection (`git ls-remote`, `git remote -v`).
- `git checkout -b <branch>` to create a local working branch.
- `git rebase` only on local, unpushed commits. If a rebase would touch anything pushed, stop and ask the user.
- `gh pr view`, `gh pr diff`, `gh pr checks`, `gh issue view`, `gh issue list` — all read-only `gh` commands are fine.

## What the agent does not do

- `git push` (any branch, any remote, any flags).
- `git push --force`, `git push --force-with-lease`, `git push --mirror`.
- `git push origin --tags` or any tag push.
- `gh pr create`, `gh pr merge`, `gh pr close`, `gh pr ready`.
- `gh repo create`, `gh release create`, `gh repo edit` with visibility/setting changes.
- Editing remote-tracking refs by hand, or running `git remote set-url` to point at a different host.
- Configuring git credentials, storing tokens in `git credential`, or writing `~/.gitconfig` for the user.
- Using any deploy or publish step that the user has not explicitly delegated in writing (and even then, prefer asking).

## Branch and commit hygiene

- Work on a feature branch, not `main`/`master`. Create the branch locally with `git checkout -b <type>/<short-desc>` from an up-to-date base.
- Keep commits small and atomic. One logical change per commit. The user reviews commits, not files.
- Branch names follow the repo's convention; if none is documented, ask the user.
- Never rewrite history of a pushed branch (`rebase`, `commit --amend` after push, `reset --hard` after push). All of those require a force-push and are user-only.

## Secrets and the push boundary

Before any commit, the agent runs the `pii-redaction` mental check on the staged diff:

- `git diff --cached` — read it line by line for keys, tokens, passwords, connection strings, real names, emails, IPs, internal hostnames, customer data. Mask anything that fails (per `pii-redaction`).
- Never commit a `.env`, `*.pem`, `*.key`, `id_rsa`, `credentials.json`, or `.npmrc` with embedded tokens. These are ignored or kept local; the agent does not bypass `.gitignore` to commit them.
- If a real secret is found in the staged diff, do not commit it. Tell the user which kind, which file, that the credential is compromised, and that rotation is the only fix.

The agent treats `git add .` / `git add -A` / `git commit -a` as red flags on any repo with `.ai/` active. They are easy ways to ship a secret or a stray file. Stage specific paths and review the diff.

## Hand-off format

When the work is ready for the user to push, the agent ends with a short, exact handoff:

- Branch name.
- List of commits added (`git log --oneline <base>..HEAD`).
- One-line summary of what changed and what was verified.
- The exact commands the user should run, ready to copy:

  ```bash
  # review
  git status
  git diff --stat <base>..HEAD

  # push (user runs this)
  git push -u origin <branch>

  # open PR (user runs this)
  gh pr create --base <base-branch> --title "<title>" --body-file <path>
  ```

- Any open threads, known caveats, or decisions the user should sign off on before pushing.

The agent does not run any of the lines under a "user runs this" comment.

## If the agent is asked to push anyway

The answer is no. Do not negotiate.

- "Just this once" — no. Push permissions are not a per-call decision; the boundary is what keeps the agent safe to use.
- "Push to my fork" — still no. Same rule.
- "Push to a feature branch I just gave you access to" — still no. The user runs the push command from their own shell.
- "It's already approved, CI will catch issues" — no. CI runs after push; the goal is for the push itself to be safe.
- "There's nothing to review" — there is always something to review, even an empty diff. The user reviews.

If the user genuinely needs the agent to act on a remote (rotating a webhook, deleting a stuck branch, closing a stale PR), the user does it from their authenticated session. The agent can stage the work, draft the command, and hand it off.

## Out of scope

- The agent does not configure CI, write deploy keys, or manage repository settings. Those are user-owned.
- Read-only `gh` commands (`pr view`, `pr diff`, `issue list`, `run view`) are fine and useful — they help the agent understand context without writing anything.
- If the repo has an automated bot account used for routine housekeeping (dependabot, renovate), the agent does not impersonate it.

## Scope

Applies to every session, every repo, every branch. Sits on top of the mandatory rules in `AGENTS.md` and the `pii-redaction` and `docker-testing` skills. The user's push is the trust boundary; the agent's job is to make sure that boundary is well-lit and never crossed.
