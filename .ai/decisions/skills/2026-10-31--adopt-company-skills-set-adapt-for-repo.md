# Adopt the company skills set and adapt for this repo

- **Date:** 2026-10-31
- **Decided by:** user (chat, this session)
- **Topic:** skills

## Decision

Bring this repo up to the `~/agent-rules/repo-template` skill set. Six skills added, one rewritten, two small-model skills skipped, one broken skill ignored.

### Added (six)

| Skill | Source | Treatment |
|---|---|---|
| `docker-testing` | `~/agent-rules/repo-template` | **Adapted.** Added a "no Docker daemon on the agent's host" fallback ladder (container → host toolchain, project-scoped only → report the gap). Replaced the global "do not fall back to the host" rule with a real fallback because the agent environment in this repo lacks Docker. Documented that `.gitignore` does **not** list `node_modules/` or `package-lock.json` (a separate issue, intentionally not fixed here). |
| `security-rbac-zero-trust` | `~/agent-rules/repo-template` | **Adapted.** Rule 4 was "Postgres RLS". This repo has no SQL — the equivalent is per-service Redis ACLs, which were added in Phase 3. New section covers Redis ACL posture: one user per service, key patterns follow data flow, read-only services are read-only by **command set** (not key patterns alone), `default` is `off`, passwords from env only. Postgres RLS still documented as the rule for any SQL service ever added. RBAC section pruned to the single-operator `ALLOWED_USER` model this repo actually has, with a "when a real role system is added, do it this way" bridge. Path-containment on worker writes added as a zero-trust note. |
| `eda-econometrics-numpy` | `~/agent-rules/repo-template` | **Trimmed.** The original is 301 lines of Kennedy econometrics (Ramsey RESET, Durbin-Watson, Breusch-Pagan, White, VIF, Jarque-Bera, Hausman IV, ridge/elastic-net/logistic/k-means in numpy). This repo has no training data and no supervised model after Phase 4. Dropped all classical assumption tests, all numpy regression implementations, the OLS/Hausman section, and the model-handoff section. Kept and rewrote: numpy-only principle, PCA-from-numpy (preferred SVD form, with a note that `core/ml/pca_engine.py` uses `eigh` on covariance and that is fine), feature-selection order as a checklist for the day a data source is wired, eval contract adapted to this repo's "no train/val/test split" reality, and the senior-gotchas rewritten for the actual risks (dormant pipeline, drift vs. novelty, `n_components=5` is a magic number, confidence is a rule margin). |
| `no-agent-push` | `~/agent-rules/repo-template` | **Copied as-is** with one added `### In this repo` note: this repo contains a Telegram bot that pushes and opens PRs as part of its product behavior. The skill governs the agent working in the repo, not the bot running in production. Without the note, a reader would see the skill and the bot and think they contradict. |
| `pii-redaction` | `~/agent-rules/repo-template` | **Copied as-is.** Identical across `agent-rules/repo-template`, `agent-rules-qwen2.5-coder/{root,repo}-template`, and `ai-gateway`. Generic and stack-neutral. |
| `repo-index` | `~/agent-rules/repo-template` | **Copied as-is** with one added `## In this repo` note: the index is **not built yet** — `.ai/index/` does not exist; building it is a separate, opt-in step (~70 source files). Do not generate it silently. |

### Rewritten (one)

| Skill | Why |
|---|---|
| `data-science` | Was: full-stack TensorFlow/Keras + FastAPI + `contract/` workflow. None of which apply here — `core/llm` deleted 2026-10-24, `contract/` folder explicitly forbidden by AGENTS.md, `core/ml` is numpy-only after Phase 4. Rewritten to describe this repo's actual pipeline: numpy PCA → statistical drift → rules-based risk → Redis → Node API → React dashboard. Drops pydantic, FastAPI, contract mirror, pandas, sklearn. Keeps the principles (start simple, know the latency budget, no redundant work, reproducible, question the data) and the senior-gotchas section, rewritten for the post-Keras risks. |

### Skipped (three)

| Skill | Source | Why skipped |
|---|---|---|
| `code-navigation` | `~/agent-rules-qwen2.5-coder/{root,repo}-template` | Tuned for a 10k-token small-context model. This repo runs on a much larger model; the discipline is redundant. |
| `context-compiler` | `~/agent-rules-qwen2.5-coder/{root,repo}-template` | Same reason. |
| `kennedy-assumption-tests` | `~/ai-gateway/.claude/skills/kennedy-assumption-tests/` | Empty directory; no SKILL.md. Source is broken, not a candidate. |

## Why

`~/agent-skills` does not exist. The real sources are the sibling skill templates under `~/agent-rules/`, `~/agent-rules-qwen2.5-coder/`, `~/ai-gateway/`, `~/opencode-pi/`, `~/webhook-switchboard/`. The canonical repo template is `~/agent-rules/repo-template` (7 skills; the others are subsets or small-model variants). This repo had only 3 of the 7 — `data-science`, `repo-memory`, `rules-site`. The missing four (`docker-testing`, `no-agent-push`, `pii-redaction`, `security-rbac-zero-trust`) plus the niche skills (`eda-econometrics-numpy`, `repo-index`) are all directly relevant to the work this repo ships.

The existing `data-science` skill was stale and actively misleading: it directed agents to use TensorFlow, FastAPI, and a `contract/` folder that the project's own AGENTS.md forbids. Phase 4 (Keras/TFLite drop) made it worse, not better. Rewriting it was the only way to avoid training future agents on a stack that does not exist here.

Adapting where it conflicts (rather than verbatim copy) is the standard the user picked from a four-option question in chat. The conflicts were real: `docker-testing`'s "no fallback to host" rule would block all verification in the agent environment, and `security-rbac-zero-trust`'s "Postgres RLS" rule would point at a database this repo does not have.

## What stays

- `repo-memory` and `rules-site` are unchanged.
- `data-science` keeps the same `name` and directory, so existing references in this repo (e.g. AGENTS.md's skill list) continue to work.
- The agent-rules standard is the canonical template. If a skill needs a future update, prefer pulling the new version from there and re-applying the same adaptation pattern.

## What changes

Six new `SKILL.md` files under `.claude/skills/`. One rewritten. Working tree now has nine skills, matching the template's coverage modulo the qwen-skipped niche and the broken `kennedy-assumption-tests` placeholder.

## Supersedes / relates to

- `.ai/decisions/security/2026-10-28--no-api-keys-in-frontend-rls-in-database.md` — the security baseline that `security-rbac-zero-trust` adapts.
- `.ai/decisions/simplify/2026-10-24--strip-llm-and-vdb-keep-bot-pca.md` — the architectural shift that invalidated the old `data-science` skill.
- Phase 4 (this session) — the Keras/TFLite drop that made the new `data-science` skill and the trimmed `eda-econometrics-numpy` necessary.
- Phase 3 (this session) — the Redis ACLs that `security-rbac-zero-trust` describes.

## Open threads

- `.ai/index/` is not built. Adding the `repo-index` skill is intentional; building the index itself is a separate opt-in task.
- `package-lock.json` and `node_modules/` are not in `.gitignore` despite the docker-testing skill having to mention it. Pre-existing repo hygiene issue; not addressed here.
- `kennedy-assumption-tests` is broken in `~/ai-gateway` — flag for that repo, not ours.
