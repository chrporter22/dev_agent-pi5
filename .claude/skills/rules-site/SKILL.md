---
name: rules-site
description: Bundle containing the static HTML viewer for the company agent-rules documents (AGENTS.md, CLAUDE.md, .ai memory README, repo-memory skill). Use when the user asks to preview, open, serve, or update the rules presentation page. Triggers: "show rules", "preview AGENTS.md", "rules site", "rules viewer", "open index.html", "serve rules page".
---

# Rules Site Skill

This skill bundles the `agent-rules/rules-site/` presentation page so it ships inside the repo and can be served or opened locally.

## What is in this folder

- `index.html` — single-file static web app (VSCode-themed). Embeds markdown source for `repo-template/AGENTS.md`, `repo-template/CLAUDE.md`, `.ai/sessions/README.md`, `.ai/decisions/README.md`, `.claude/skills/repo-memory/SKILL.md`, and `README.md` from the agent-rules repo. Renders them with a built-in markdown renderer, search, dark/light toggle. **Self-contained: no build step, no network calls.**

## How to view it

Pick whichever the user asked for:

- **Open directly** in a browser (file path or `file://` URL). Works as-is.
- **Serve locally** with any static server, for example:

  ```bash
  cd .claude/skills/rules-site
  python3 -m http.server 8000
  # then open http://localhost:8000/
  ```

  Pick a free port. Do not use a port already bound by a service in this repo (the dashboard uses 80, `node-api` uses 3000, `vdb` uses 8081, `llm` uses 8080).

## When the rules source changes

The `index.html` carries a build-time-injected `DOCS` constant near the top. If `repo-template/AGENTS.md`, `repo-template/CLAUDE.md`, the `.ai/` READMEs, or the `repo-memory/SKILL.md` change in `~/agent-rules/`, this copy goes stale.

- Do **not** edit the embedded markdown by hand — the file says so itself.
- Tell the user the bundled HTML is out of sync, point them at the source-of-truth files in `~/agent-rules/repo-template/`, and ask whether to rebuild the viewer there and re-copy it into this folder.

## What this skill is not

- It is not a rules source of truth. The rules live in `AGENTS.md` at the repo root. Follow those, not this viewer.
- It does not inject rules into the agent's instructions. It is a human-facing presentation page.
