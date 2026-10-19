# Mandatory Agent Rules

These rules apply to every agent working in this repository. They are mandatory unless the user explicitly overrides them for a specific task.

## Highest Priority

Plan first. No quick fix. Work as a single agent — do not use workers or sub-agents.

- Treat this as the most important repository instruction for every run.
- If any task request feels urgent, small, or obvious, still plan first before changing code.
- Do not bypass this workflow unless the user explicitly says to ignore these repo rules for that specific task.

## Read Memory First

Every session starts by reading repo memory before any planning or code work:

1. Read `.ai/decisions/` — browse topic folders relevant to the task and read the decision files inside. This is where the business "why" behind the codebase lives.
2. Read `.ai/sessions/` — find recent session files in topic folders relevant to the task. This is the AI work history: what was done before, what's unfinished, what was tried and rejected.
3. Only read what is relevant to the task. Do not load everything.

The full workflow for reading and writing these folders is in the `repo-memory` skill (`.claude/skills/repo-memory/SKILL.md`). Follow it in every session.

## No Workers or Sub-Agents

- Do not spin up worker agents, sub-agents, or parallel agent tasks for exploration, implementation, or review.
- All work — codebase exploration, planning, implementation, verification — is done directly by the single agent in the main session.
- This keeps the full context of the task in one place and every change reviewable in one thread.

## Agent Role

- The agent plans, brainstorms, coordinates with the user, implements, and reviews its own work.
- The agent must ask clarifying questions as needed. It should not rush from an unclear request into implementation.

## Planning and Approval Workflow

- Before implementation, the agent must discuss the approach with the user and produce a concrete plan.
- Implementation must not begin until the user approves the plan and explicitly asks the agent to proceed.
- After approval, the agent must break the plan into ordered subtasks before any code changes start.
- The agent must work through subtasks sequentially, completing and reviewing the current subtask before starting the next.

## Code Quality Rules

- Do not overcomplicate the codebase.
- Do not use quick fixes, hacks, or brittle patches.
- Do not optimize only for getting the latest bug fix or feature shipped.
- Every change must align with the existing architecture, style, naming, and patterns of the repository.
- Keep solutions clean, minimal, and maintainable.
- Avoid unnecessary abstractions, high-level design patterns, framework churn, or broad refactors.
- Prefer small, direct changes that reduce or preserve technical debt.
- Be careful about side effects and regression risk. Consider how a change interacts with nearby code and existing behavior.
- If the clean path is unclear, stop and ask questions during planning instead of guessing.

## Verification

- The agent must run the relevant checks (tests, type checks, lint, build) for each subtask when practical, and review the results before moving on.
- If checks cannot be run, the agent must report that clearly and explain the remaining risk.

## Memory Discipline

- `.ai/sessions/` — AI work history. One new file per local session, always. Never append to a previous session's file.
- `.ai/decisions/` — business decision history. High-level business decisions and project business logic only; the "why", never code detail.
- Both folders are organized as one level of topic folders with one file per session inside. Reuse an existing topic folder if one matches; only create a new one if nothing fits.
- Write the session file as you work and finalize it before the session ends. Record decisions the moment the user confirms them.
- Never hallucinate. If a fact is not in memory, in a plan, or in code, ask the user.

## Repository Layout

This repository is a single git repo, not a parent directory holding separate repos. Agents are spun up from the repo root and work across all of it.

- `core/<service>/` directories are sub-projects of this one repo, not separate repos. Each has its own `README.md` written as a PRD/spec, its own Dockerfile, and its own dependencies.
- This root `AGENTS.md` and `CLAUDE.md` apply to the whole repo, including every `core/<service>` and the root compose files. There is no per-service `AGENTS.md` unless one is added deliberately.
- All memory lives in the single root `.ai/` (`.ai/sessions/` and `.ai/decisions/`), following the `repo-memory` skill.
- A task spanning several services still gets exactly one session file, in the root `.ai/sessions/`, under a topic folder matching the work. Do not create a `.ai/` inside a service directory.
- Never write memory files, code, or config outside `.ai/` and the service directories. The repo root holds compose files, install scripts, docs, and agent config only.
- Git operations (branch, commit) happen at this repo root. This repo never commits into another repo.

---

# Engineering Standards

These are the company-wide defaults. They were written for a TypeScript/Node/React + MongoDB stack, and this repo is a Python + TypeScript + Redis/SQLite container stack, so a number of them do not apply. The Project-Specific Rules at the bottom of this file list every deviation explicitly. Check them before applying anything below, and never silently ignore a standard.

Standard engineering stack: TypeScript everywhere, Node backend, React + Vite frontend, MongoDB, zod for validation.

## API Contract Is the Single Source of Truth

Applies to every project with a frontend/backend split.

- The canonical contract lives in the frontend repo under `contract/`. The frontend side owns it and edits it first.
- The backend repo keeps a local mirror at `contract/`. It is byte-identical at each cutover, updated by hand-copying changed files from the frontend repo when implementing a contract change. The backend's own `CHANGELOG.md` is frozen as a historical record — do not append to it.
- Backend imports the contract via relative paths from its local mirror (e.g. `import { exchange } from "../../../contract/endpoints/auth.contract"`). No npm linking, no shared contract package wrapper. The contract folder has no `package.json`.
- Frontend reads the canonical folder via a Vite path alias `@contract` → `./contract` (local to the frontend repo). Neither deploy needs the other repo at build time, and the repos do not need to be cloned side-by-side.
- Every API change starts by editing files under the frontend's `contract/` and appending an entry to the frontend's `contract/CHANGELOG.md` with status `needs-implementation`, the file changed, a summary, and the requesting side. That changelog is the live ledger for both sides.
- The backend agent landing the implementation hand-copies the changed contract files into the backend's `contract/`, implements the change, and flips the entry in the frontend's `CHANGELOG.md` to `done`.
- Backend zod validation imports schemas exclusively from its local `contract/` mirror — never re-defines request/response schemas in route files.

## Code Organization

- No JSON-driven workflow engines or config-defined business flows. Ever.
- Business logic lives in plain TypeScript orchestrator files. Each action gets its own file under `modules/<feature>/actions/<actionName>.action.ts`. Reading the file top-to-bottom describes the workflow in English.
- Helpers live as named exports on a static-style namespace object (e.g. `InvitationHelper.x()`), not class methods bound to `this`.
- Duplication > premature reuse in the first iteration. Refactor only when ≥3 call sites genuinely share behavior.
- No DI framework, no service container, no event bus. Plain imports.
- Files stay small. If an action file passes ~250 lines, split it.

## Persistence and Ops

- **Soft delete only.** Every collection has a `deletedAt: Date | null`. Hard deletes require explicit user approval.
- **Multi-tenant projects:** every collection carries the tenant key (e.g. `organizationId`) and indexes lead with `(organizationId, deletedAt, …)`.
- **Structured logging** with separate datasets/streams per environment (`<project>-dev`, `<project>-prod`). Default level: `info` in prod, `debug` in dev. Every action runs inside a logging context carrying `{ requestId, userId, action }` (plus tenant id where applicable). The logging vendor is set per project in the project-specific rules.
- **Encryption at rest:** all third-party credentials and API keys stored in the database are AES-256-GCM encrypted using a master key from env (`APP_ENCRYPTION_KEY`). Never store secrets in plaintext.
- **Auth:** Firebase Auth on the client → custom JWT exchange on the backend. Token sent via `Authorization: Bearer …` header. Multi-tenant projects pass the active tenant per request via an `x-org-id` header.

---

# Project-Specific Rules

These sit on top of the mandatory rules and engineering standards above. Where they conflict with the Engineering Standards, they win.

## What this project is

DEV AGENT Pi — a zero-trust, fully containerized AI + analytics stack for a Raspberry Pi 5 (ARM64, 16GB, Arch Linux). Request path:

`Telegram → core/bot → core/llm → core/vdb → core/node-api → core/ml → core/pca-backend`

## Deviations from the Engineering Standards

- **No MongoDB.** Persistence is SQLite via `sqlite-utils` in `core/vdb`. SQLite is the source of truth; `/data/index.bin` (FAISS `IndexFlatIP`) is a disposable derived index rebuilt from SQLite. Redis is a cache and job transport only, never a source of truth.
- **No zod.** Validation is hand-written per service.
- **Not TypeScript everywhere.** `core/bot`, `core/llm`, `core/ml`, `core/vdb` are Python. `core/node-api` and `core/pca-backend` are TypeScript.
- **No `contract/` folder.** `core/pca-backend` consumes `core/node-api` over HTTP through the nginx `/api/` proxy. There is no shared contract package, and `core/node-api` is strictly read-only over ML state: it must never compute PCA, retrain, or write ML keys.
- **No `modules/<feature>/actions/` layout.** Services are organized by concern inside the service directory.
- **Soft delete, multi-tenancy, and Firebase Auth do not apply.** There is no multi-tenant SaaS layer and no Firebase. The only auth is a Telegram bot token in env.

## Services

- `core/bot` — `openclaw-bot` + `openclaw-worker`. Telegram polling, LLM command parsing, Redis job queue, creates `feature/<uuid>` branches and opens PRs. Never touches the host, the shell, or `main`.
- `core/llm` — `openclaw-llm`. llama.cpp built from source on `ubuntu:22.04` plus a Flask gateway. Stateless inference only; `POST /parse` returns strict JSON with no prose or markdown. Outbound DNS is disabled (`dns: []`).
- `core/ml` — `openclaw-ml`. Background analytics loop with no HTTP API and no exposed ports. Embedding ingest → PCA (pure numpy, top 5 components) → drift detection → risk classification → Keras single-hidden-layer model with random hyperparameter search → TFLite export. Writes every output to Redis (`pca:*`, `drift:*`, `risk:latest`, `model:*`, `ml:heartbeat`, `ml:last_run`).
- `core/vdb` — `openclaw-vdb`. FastAPI + FAISS + sentence-transformers semantic memory. Internal API on 8081: `POST /embed`, `POST /upsert`, `POST /search`, `GET /health`.
- `core/node-api` — Express/TypeScript read-only ML layer on 3000, endpoints under `/api/ml/`.
- `core/pca-backend` — React + Vite + Recharts + Tailwind dashboard served by nginx. **The only public ingress (80:80).**

## Stack and style

- Python 3.11 (`core/bot`, `core/ml`) and 3.12 (`core/vdb`). Type hints are used in `core/vdb` and absent in `core/ml` — match the file you are editing, do not add or remove them repo-wide.
- Each Python service has a module-level `config.py` reading `os.getenv` with defaults and feature flags. Do not read env vars inline elsewhere.
- Tests are stdlib `unittest` only, in `core/vdb/tests/`, imported as `core.vdb.app.*`. There is no pytest, no tox, and no coverage config.
- TypeScript: Node 22, double quotes, **no semicolons**, 2-space indent, `camelCase`.
- React files live in `core/pca-backend/src/components/{ui,cards,charts,header}/`, hooks in `src/hooks/use*.ts`, types in `src/types/*.ts`, config at the service root.
- Code comments use this repo's banner style: an all-caps title wrapped in rule characters, the file path on the first line, and `STEP 1 —` markers. Python uses `# --------------------------` or `# ==========================`; TypeScript uses `// ----------------------------------`.
- TypeScript call sites are written vertically exploded — one argument or destructured binding per line. Match it.

## Verification commands

- `core/vdb` tests, from the repo root: `python3 -m unittest core.vdb.tests.test_vdb` (or `test_api`, `test_performance`). They import `core.vdb.app.*`, so the repo root must be the working directory, and `core/vdb/requirements.txt` must be installed — `faiss` and friends are container-only and are not on the host by default. An import error for a missing dep is an environment problem, not a code regression.
- `core/node-api`: `npm run build` (tsc) in `core/node-api`.
- `core/pca-backend`: `npm run build` (tsc + vite) in `core/pca-backend`. `npm run lint` is declared but **broken** — eslint is not in devDependencies and no config file exists. Do not treat its failure as a regression you caused.
- **There is no repo-wide lint, format, or test command.** No Makefile, no CI, no pre-commit hooks, no Python linter or formatter. Verify per service and report what you could not run.
- The root `.dockerignore` is effectively unused: every compose service uses `context: ./core/<service>`, so the root file never applies to a build.

## Docker and compose

- `docker-compose.prod.yml` is authoritative: all 7 services, with `pca-backend` as the only published port.
- `docker-compose.yml` is stale and dev-only. It is missing `node-api`, `openclaw-ml`, `pca-backend`, and `redis`, and it publishes `8081:8081`, which contradicts the internal-only rule. Never "fix" the prod file to match the dev file.
- Every service runs `read_only: true` with tmpfs, `cap_drop: ALL`, and `no-new-privileges`. Keep it that way.
- Secrets come from env only. The templates are the root `.env.example` and `core/vdb/.env.example`; `.env` itself is gitignored.

## Known-broken, pre-existing

These are already broken on `main`. Do not re-diagnose them mid-task and do not bundle unrelated fixes into a change. Fix one only when the task calls for it, and say so in the plan.

- `core/pca-backend/src/main.ts` contains JSX and must be `main.tsx`. It imports `./styles/globals.css` while the file on disk is `global.css`. `src/App.tsx` has a line-broken `import Dashboard\nfrom "./pages/Dashboard"` with no semicolon. There is no `core/pca-backend/index.html` even though `vite.config.ts` and `tailwind.config.ts` expect one.
- `core/node-api/src/routes/ml.ts` imports `../utils/redisHelpers`; the file on disk is `redisHelper.ts`.
- `core/vdb/Dockerfile` has `COPY ./bootstrap /app/bootstrap`; no `bootstrap/` directory exists.
- `core/llm/llm-server/start-llm.sh` starts llama.cpp on 8081 while the Dockerfile `EXPOSE 8080` and `LLAMA_ENDPOINT` point at `http://openclaw-llm:8080`.
- `install.sh` still contains the placeholders `MODEL_URL="https://YOUR_MODEL_DOWNLOAD_URL"` and `MODEL_SHA256="REPLACE_WITH_EXPECTED_SHA256_HASH"`, so it cannot complete as written.
- `bootstrap_vdb.sh` calls `python3 ./core/vdb/populate_volume.py`; the file is at `core/vdb/scripts/populate_volume.py`.
- The root `README.md` is a TODO/PRD/security-spec hybrid rather than a project README, and its `docker compose up -d` instructions do not start the three newer services.

## Memory notes for this project

- Worth recording in `.ai/decisions/`: the split of responsibility between `node-api` and `ml`, the SQLite-as-source-of-truth rule, why `pca-backend` is the only ingress, and any change to the Telegram → branch → PR flow.
- The zero-trust constraints and the bot/PR security model are deliberate decisions, not incidental. Record the reasoning before changing them.
