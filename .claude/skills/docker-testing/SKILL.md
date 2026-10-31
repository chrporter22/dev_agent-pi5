---
name: docker-testing
description: Run all tests, builds, lint, type checks, and dev tooling inside Docker — never install dependencies or toolchains on the local machine. Use whenever verification is needed (running the test suite, build, lint, type check, migrations, or any CLI tool of the project), and before running any install command. Triggers: "run the tests", "does it build", "lint it", "type check", running the app, `npm install`, `pip install`, `poetry add`, `apt-get install`, `brew install`, or any command that would add packages to the host.
---

# Docker-Only Testing

Every test, build, lint, type check, and dev command runs **inside a container**. The local machine is for editing files and running git — nothing else. Nothing gets installed on the host: not project dependencies, not language runtimes, not CLI tools, not global packages.

The reason: a test that only passes because someone's laptop happens to have the right Node version, a global `tsc`, or a half-installed `node_modules` is not a real signal. Containers make the environment explicit, reproducible, and identical to CI. And they keep the host clean — an agent that runs `npm install` on the host has silently mutated the user's machine.

## The two rules

1. **Run everything in Docker.** Tests, builds, lint, type checks, codegen, migrations, the app itself.
2. **Install nothing on the host.** No `npm install` / `yarn` / `pnpm` outside a container, no `pip install`, no `poetry add`, no `apt-get`, no `brew`, no `nvm install`, no global installs. The host may not even have the runtime the project needs — that is fine and expected.

## How to run tests

Use the repo's existing Docker setup. Check for it before doing anything:

- `compose.yaml` / `docker-compose.yml` → prefer `docker compose run --rm <service> <command>` (or `docker compose exec <service> <command>` against a running stack).
- `Dockerfile` / `Dockerfile.dev` → `docker build` then `docker run --rm <image> <command>`.
- A project `Makefile` or `package.json` scripts that already wrap Docker → use those; they encode the project's intended entry points.

Example shapes (adapt to the repo's own services and commands):

```bash
docker compose run --rm app npm test
docker compose run --rm app npm run lint
docker compose run --rm app npm run typecheck
docker compose run --rm api pytest
docker build -t project:dev . && docker run --rm project:dev pytest
```

## This repo's compose files

`docker-compose.prod.yml` is **authoritative** — all six services, with `pca-backend` as the only published port. `docker-compose.yml` is stale and dev-only: it is missing `node-api`, `openclaw-ml`, `pca-backend`, and `redis`, and it publishes `8081:8081`. Do not "fix" the prod file to match the dev file, and do not use the dev file to infer the service list.

Service names in the prod file: `redis`, `openclaw-bot`, `openclaw-worker`, `openclaw-ml`, `node-api`, `pca-backend`.

## When the Docker daemon is unavailable

Some agent environments have the repo but no running Docker daemon. That is a **host limitation, not a missing Docker setup** — the repo already ships Dockerfiles and a compose file, so rule 2 (do not add a Docker setup) does not apply.

When `docker` cannot reach a daemon, fall back in this order and say which rung you landed on:

1. **Container** — `docker compose -f docker-compose.prod.yml run --rm <service> <command>`. Preferred.
2. **Host toolchain, project-scoped only** — run the repo's own documented verification commands using the toolchain already present on the host, installing dependencies **inside the service directory only** (`core/<service>/node_modules`), never globally and never outside the repo. This rung exists because this repo's verification commands are the container build steps themselves and cannot be skipped.
3. **Report the gap** — if neither rung is possible, state plainly which check did not run and what the remaining risk is. Never silently skip verification, and never claim a check passed that did not run.

What counts as a project-scoped host install (rung 2) and is acceptable:

- `npm install` inside `core/node-api/` or `core/pca-backend/` — creates a repo-local `node_modules`, does not touch the system.
- `python3 -m venv` inside the repo, or `pip install --user`-free use of an existing interpreter.

What is never acceptable on the host:

- `sudo apt-get install`, `brew install`, global `npm install -g`, `nvm install`, `pip install` into the system interpreter.
- Installing a language runtime the host does not have.

A note on the working tree: this repo's `.gitignore` covers `dist/` but does **not** list `node_modules/` or `package-lock.json` — they will show up as untracked after a host-side `npm install`. Add them to `.gitignore` only as a deliberate change, not as a side-effect of running the build. If a host install is used, note it in the session record and confirm with `git status -u` that nothing build-artifact-shaped was created in tracked paths before the session ends.

## If there is no Docker setup

Do not fall back to the host. The absence of a Docker setup is the thing to fix:

1. Write a minimal `Dockerfile` (and `compose.yaml` if the project needs services like a database) that installs dependencies **inside the image** and can run the test command.
2. Run the tests through it.
3. Tell the user you added the container setup, and why.

Adding a Dockerfile is a code change like any other: keep it minimal, match the project's stack and conventions, and put it up for review — do not quietly invent a heavy multi-stage build.

## When local dependencies look missing

If `npm test` fails because `node_modules` doesn't exist, or a tool "isn't installed", that is not a reason to install it on the host. Run the install inside the container (it should already be part of the image build). If the runtime itself is missing on the host, that is the expected state — go straight to Docker.

## Rules of thumb

- Prefer `docker compose run --rm` over leaving containers lying around; clean up after yourself.
- Mount the repo as a volume so the container tests the current working tree, not a stale copy — or rebuild the image if the project's setup expects a baked-in copy.
- Never run `sudo` to install a tool for verification. If it can't run in Docker, report that and ask — don't mutate the host.
- If something genuinely cannot be containerized, stop and ask the user before installing anything on the local system.
- Report results from the container run. "Tests pass in Docker" is the only pass that counts; "works on the host after I installed X" is not.

## Scope

Applies to the agent's own verification runs and any command it executes while working. It does not override a project's documented setup steps for the human developer. When the repo already documents a specific Docker workflow, follow that; this skill is the default when none is given.
