# Add rules-site skill

- **Date:** 2026-10-19 20:13
- **Developer:** agent
- **Topic:** skills

## Request

User asked to copy `~/agent-rules/rules-site/` into this repo "as a skill". Source dir held only `index.html` — a self-contained VSCode-themed presentation viewer for the agent-rules documents, not skill-shaped content. Asked the user how to interpret "as a skill" before touching anything; user picked:

- Wrap as a real skill (YAML frontmatter + description in a `SKILL.md`, keep the HTML alongside).
- Place under `.claude/skills/rules-site/`.
- Do not commit.

## What was done

- Created `.claude/skills/rules-site/` and copied `index.html` from `~/agent-rules/rules-site/` byte-for-byte (68377 bytes, `diff -q` confirmed).
- Wrote `.claude/skills/rules-site/SKILL.md` (39 lines) with `name: rules-site` frontmatter and a description that triggers on "show rules", "preview AGENTS.md", "rules site", "open index.html", "serve rules page", etc.
- SKILL.md body explains what's in the folder, how to view or serve it, what port to avoid (8000 — repo already has 80/3000/8080/8081 bound), and the rule that embedded markdown must not be edited by hand: the bundled HTML is build-time-injected and will go stale if `repo-template/AGENTS.md` etc. change in `~/agent-rules/`.
- Verified frontmatter parses, file tree matches the skill convention used by `data-science/` and `repo-memory/`, and `git status` shows the new dir as untracked (no commit, per user).

## Notable findings

- `rules-site/index.html` is a single-file static site: it embeds markdown for `AGENTS.md`, `CLAUDE.md`, the two `.ai/` READMEs, `repo-memory/SKILL.md`, and the agent-rules `README.md` as a build-time-injected `DOCS` constant. Editing those blocks by hand violates the file's own comment "do not edit by hand" — the right workflow is rebuild from source, then re-copy.
- The source dir is shared with other agent-rules templates (`repo-template/`, `root-template/`). It is not a skill in `~/agent-rules/`; the wrapping `SKILL.md` is what makes it loadable here.
- Repo-wide rule reminder: `.claude/skills/` is pre-approved for skill content; this addition stays inside that area.

## Open threads

- Bundled HTML will drift the next time `repo-template/AGENTS.md` or the other embedded docs change. Not worth automating here — flag to the user when it matters.
- Not committed, per user request. User may commit on a `feature/<name>` branch later via the bot/PR flow.
