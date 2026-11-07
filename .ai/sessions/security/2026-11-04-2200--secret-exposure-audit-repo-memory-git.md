# Secret exposure audit across repo, memory, and git

- **Date:** 2026-11-04 22:00
- **Developer:** user (chat, this session)
- **Topic:** security

## Request

User asked whether any of their API keys are present in the working repository, the session
memory (`.ai/`), or git history. Session was labelled `LITELLM ESCALATE`, which per
`.ai/decisions/llm/2026-10-31--litellm-escalate-interpretation.md` is a project-internal label
for the `/chat` code path, not a mode change — so this was handled as a read-only audit with
no behaviour override.

## What was done

Read-only audit. No code, config, or git history was changed.

1. **Working tree** — scanned every file (including dotfiles and ignored files) for known
   credential shapes: `sk-…`, `sk-ant-…`, `ghp_`/`gho_`/`github_pat_`, `AKIA…`, `xox[baprs]-…`,
   `AIza…`, `hf_…`, PEM private-key headers, and Telegram bot-token format (`<digits>:<35 chars>`).
2. **Generic sweep** — searched for `key|token|secret|password|credential` assignments with
   non-placeholder values, then filtered out env reads (`os.getenv`, `process.env`), shell
   interpolation (`${VAR}`), and documentation placeholders.
3. **Session memory** — searched `.ai/decisions/` and `.ai/sessions/` for credential shapes,
   credential *names*, and network identifiers (IPv4, internal hostnames, URLs).
4. **Git history** — enumerated every blob reachable from every ref (all 33 commits, 257 blobs)
   and ran the same pattern set across each blob's content, then mapped each hit back to its
   file path via `git rev-list --objects`. Also checked for dangling/unreachable objects, stashes,
   git notes, and the full reflog.
5. **Build-context check** — confirmed every compose service builds from `context: ./core/<service>`,
   so the repo-root `.env` is never inside a Docker build context; it is only mounted at runtime
   via `env_file`.

## Notable findings

- **Git history is clean.** All nine pattern hits across the 257 historical blobs are
  placeholders in `.env.example`, `core/llm/README.md`, and two `.ai/` files — values like
  `your_litellm_api_key_here`, `your_scoped_virtual_key_here`, `your_telegram_bot_token_here`,
  `ghp_replace_me`, `your_github_pat_here`. No real credential was ever committed.
- **Session memory is clean.** `.ai/` records env var *names* only (`AI_GATEWAY_API_KEY`,
  `GITHUB_TOKEN`, `REDIS_PASSWORD`, `TELEGRAM_TOKEN`) and the standard placeholder examples. No
  credential values. The only network identifier present is the Docker default bridge address
  (`172.17.0.1`), which is generic infrastructure, not a host identifier.
- **Tracked working tree is clean.** `git grep` over `HEAD` returns zero hits for every
  credential pattern. `docker-compose.prod.yml`, `redis/users.acl.template`, `redis/entrypoint.sh`,
  `contract/`, and the root docs are all placeholder- or interpolation-only.
- **`.env` at the repo root holds the only real secrets.** The file is gitignored and untracked
  (confirmed via `git ls-files --error-unmatch .env`), so it exists only on this machine.
  It currently carries a real LiteLLM gateway virtual key (`AI_GATEWAY_API_KEY`=<REDACTED:API_KEY>),
  the shared `REDIS_PASSWORD`=<REDACTED:PASSWORD>, and four per-service Redis passwords
  (`REDIS_PASSWORD_BOT`/`_WORKER`/`_ML`/`_NODEAPI`)=<REDACTED:PASSWORD>. The gateway key appears
  nowhere else in the tree — it is confined to `.env`.
- **Three `.env` values are still placeholders**, not real: `TELEGRAM_TOKEN`, `GITHUB_TOKEN`, and
  `ALLOWED_USER` (still `0`). Those three are the remaining blockers for an end-to-end bot run.
- **`REDIS_PASSWORD` duplicates `REDIS_PASSWORD_WORKER`.** Not a leak, but a config smell worth
  flagging: the shared value means any service started with the legacy shared password still has
  the worker-level credential.

## Open threads

- **Rotation is the user's call.** The LiteLLM gateway virtual key is a live third-party
  credential stored in plaintext on disk. It is correctly outside git, but it is still one disk
  read (or one careless backup) away from being exposed. Rotating it is cheap; masking the file
  afterwards would not be.
- **The pre-commit secret scan remains deferred.** `.ai/decisions/security/2026-10-28--no-api-keys-in-frontend-rls-in-database.md`
  lists an automated scanner (gitleaks / trufflehog) as "deferred to user, worth doing, not
  blocking". This audit was manual and one-shot; a hook would make it continuous.
- **No leak occurred, so no incident note is required.** Nothing was rewritten or removed from
  history, and no credential was written into `.ai/`.
