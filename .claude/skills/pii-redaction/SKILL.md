---
name: pii-redaction
description: Mask secrets, API keys, tokens, passwords, connection strings, usernames, emails, IPs, hostnames, and any other PII before writing anything into `.ai/sessions/` or `.ai/decisions/`. Those folders are committed and pushed to GitHub, so anything written there becomes public repo history forever. Triggers: writing or updating any file under `.ai/`, "record this decision", writing a session file, or pasting env vars, config, `.env` contents, connection strings, curl output, stack traces, log excerpts, user records, or real data into memory.
---

# PII & Secret Redaction for `.ai/` Memory

`.ai/sessions/` and `.ai/decisions/` are committed to git and pushed to GitHub. Git history is permanent: a value written once is readable by everyone with repo access — including forks, mirrors, caches, and scrapers — even after a later commit "removes" it.

So the rule is simple: **memory files describe values, they never contain them.** Any credential, identifier, or personal datum goes in as a masked label.

## The rule

Before writing any value into a `.ai/` file, ask: *would this be a problem if it leaked?*

- Yes → write the masked label, not the value.
- It is a generic placeholder (`example.com`, `your-project-id`, `xxx`) already → keep it.
- Unsure → mask it and tell the user which labels you used, so they can override.

Never write the raw value "temporarily" to be edited later. Assume every version you write gets committed.

## Masking labels

Use these exact labels. Consistency is what makes the memory useful — the next agent knows what each label refers to without seeing the secret.

| Real thing | Write this | Never write |
|---|---|---|
| API key, access token, bearer token | `<REDACTED:API_KEY>` | the key, or any partial prefix/suffix of it |
| Password / passphrase | `<REDACTED:PASSWORD>` | the password |
| Private key, PEM, keystore, seed phrase | `<REDACTED:PRIVATE_KEY>` | any part of the key material |
| DB / connection string | `<REDACTED:DB_URL>` | `postgres://user:pass@host:5432/db` |
| OAuth client secret, webhook secret, signing secret | `<REDACTED:SECRET>` | the secret |
| Env var value (any `*_KEY`, `*_TOKEN`, `*_SECRET`, `*_PASSWORD`) | `VAR=<REDACTED:ENV_VALUE>` | the value |
| Master key / encryption key | `<REDACTED:MASTER_KEY>` | the key |
| Real username / login / operator account | `<REDACTED:USERNAME>` | the username |
| Real person's name | `<REDACTED:PERSON>` | the name |
| Email address | `<REDACTED:EMAIL>` | the address |
| IPv4 / IPv6 address | `<REDACTED:IP>` | the address |
| Internal hostname, service DNS name, k8s namespace, server name | `<REDACTED:HOST>` | the hostname |
| Public/staging URL that is not public knowledge | `<REDACTED:URL>` | the URL |
| Customer / user data, record IDs, phone, address, DOB, payment info | `<REDACTED:CUSTOMER_DATA>` | the record or field values |
| Vendor account / org / tenant IDs | `<REDACTED:ORG_ID>` | the ID |
| S3 bucket, project, or resource ID from a cloud console | `<REDACTED:RESOURCE_ID>` | the ID |

Keep what is safe: file paths, module names, port numbers in a config, env var *names*, error messages, stack frames, log lines that contain no sensitive values, and the non-sensitive half of a connection string (`postgres://<REDACTED:USERNAME>:<REDACTED:PASSWORD>@<REDACTED:HOST>:5432/<REDACTED:DB_NAME>`).

## What triggers masking

- Reading a `.env`, `.env.*`, `*.pem`, `*.key`, `credentials.json`, `.npmrc`, `id_rsa`, or `secrets/` file.
- Debugging auth, payments, or integrations — exactly when values are most likely to be pasted.
- Pasting command output: `env`, `printenv`, `docker inspect`, `kubectl get secret -o yaml`, `psql` output, `curl -v` (headers carry cookies and tokens), stack traces with connection strings.
- Quoting user records, test data, or anything copied from production.
- Screenshots, log excerpts, or PR descriptions pasted into memory.

## Examples

Instead of this:

```markdown
Set `STRIPE_SECRET_KEY=sk_live_51H8xQ2eZvKYlo2C...` in the backend `.env`, then restart the
container. The dev database is `postgres://appuser:hunter2@10.4.11.22:5432/prod_shadow` and
we rotate `APP_ENCRYPTION_KEY` with ops. Ping jordan.lee@company.com if the token expires.
```

Write this:

```markdown
Set `STRIPE_SECRET_KEY=<REDACTED:API_KEY>` in the backend `.env`, then restart the
container. The dev database is
`postgres://<REDACTED:USERNAME>:<REDACTED:PASSWORD>@<REDACTED:IP>:5432/prod_shadow` and
we rotate `APP_ENCRYPTION_KEY=<REDACTED:MASTER_KEY>` with ops. Ping <REDACTED:PERSON> if the
token expires.
```

The second version is just as useful to the next agent: it names the variables, the shape of
the connection string, the port, and where the secret lives — and leaks nothing.

## Before writing

1. Re-read the content you are about to add, line by line, specifically hunting for: `key`, `token`, `secret`, `password`, `pass`, `pwd`, `auth`, `://`, `@`, digits-and-dots that look like IPs, real names, email addresses.
2. Paste your draft through this mental test: *if this file were on a public GitHub repo, what would I regret?*
3. Mask anything that fails, and keep the variable name so the memory stays actionable.
4. If the whole line is about a credential's value, record the **name** of the credential, where it lives, and how to rotate it — never the value. Those are the facts a future session needs.

## Before committing

- `git diff --cached .ai/` and read the added lines. Any raw credential or PII in the diff gets masked before commit, not after.
- Never `git add` a file you have not read for secrets.
- Do not use `git add -A` / `git commit -a` on a repo with `.ai/` active without reviewing the staged diff first.

## If you already leaked a value

A leaked credential is compromised — masking the file afterwards does **not** fix it. Git history still holds it.

1. Stop. Say so plainly in the session file: *which kind of value*, *which file*, *when*. Never re-quote the value itself.
2. Tell the user the credential must be rotated, and that history rewriting (e.g. `git filter-repo`, or rewriting and force-pushing) plus GitHub support for cached views is required. Rotation is the only real fix.
3. Mask the value in the file with a note that it was rotated.
4. `.ai/` files are history records — never silently rewrite them to hide the incident. Leave the sanitized note.

## Scope

Applies to everything written into `.ai/sessions/`, `.ai/decisions/`, and any commit message or PR body produced by the agent. It does not replace the repo's real secret handling: keep secrets out of the codebase in the first place, with `.env` ignored, secrets from the environment, and a secret-scanning pre-commit hook. This skill is the last line of defense for memory, not the first.
