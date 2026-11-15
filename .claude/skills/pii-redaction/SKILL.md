---
name: pii-redaction
description: Mask secrets, API keys, tokens, passwords, connection strings, usernames, emails, IPs, hostnames, account/chat ids, and any other PII before writing anything into `.ai/sessions/` or `.ai/decisions/`. Those folders are committed and pushed to GitHub, so anything written there becomes public repo history forever. Covers partial and composite credentials (never keep a fragment of a token; never keep one half of a `id:secret` pair). Triggers: writing or updating any file under `.ai/`, "record this decision", writing a session file, or pasting env vars, config, `.env` contents, connection strings, curl output, stack traces, log excerpts, user records, or real data into memory.
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
| Bot / account numeric id (Telegram bot id, chat id, user id) | `<REDACTED:ACCOUNT_ID>` | the numeric id |
| Chat / user id of a **real person** | `<REDACTED:PERSON_ID>` | the numeric id |

Keep what is safe: file paths, module names, port numbers in a config, env var *names*, error messages, stack frames, log lines that contain no sensitive values, and the non-sensitive half of a connection string (`postgres://<REDACTED:USERNAME>:<REDACTED:PASSWORD>@<REDACTED:HOST>:5432/<REDACTED:DB_NAME>`).

## Partial and composite secrets

This is where leaks actually happen. Two rules cover it.

**A partial secret is still a secret.** Masking the middle of a token and keeping the ends does not
make it safe. `ghp_abc…wxyz` tells an attacker the format, the issuing service, and the length.
Never write a prefix, a suffix, a "first 4 characters", or an elided middle of a credential — no
matter how short the fragment is. Use the whole masked label instead.

The temptation is to keep a few characters "because they're not enough to use". That reasoning is
wrong: the fragment still narrows the search space, still confirms which service issued the
credential, and still means the credential must be treated as leaked.

**Composite credentials are one secret, not two.** Some credentials are a pair joined by a
separator — Telegram bot tokens are `bot_id:secret`, database URLs are
`user:password@host`, GitHub URLs embed `user:token@host`. The **whole string** is masked with a
single label. Do not keep the leading half because it "looks like an id" or "looks public".

```
✗  /bot1234567890:AbCd…/getUpdates
✗  postgres://appuser:hunter2@10.4.11.22:5432/prod_shadow
✓  /bot<REDACTED:API_KEY>/getUpdates
✓  postgres://<REDACTED:DB_URL>
```

**A non-secret id embedded in a secret is still masked.** If a credential happens to contain a
public-looking id (a bot's own numeric id), that id does not become safe to write out *because it
is public on its own*. It is inside the secret, so it gets masked with the secret.

The exception is an id standing **alone**, on its own, not attached to any credential — a chat id
referenced by a log line that contains no token. That is still masked by default (see
`<REDACTED:ACCOUNT_ID>`), because ids are personal-ish data and cheap to mask.

**Judge by the whole line, not by the value.** Before writing any id, token, or key-looking string,
ask: *is this line part of, or attached to, a credential?* If yes, mask the whole thing.

## What triggers masking

- Reading a `.env`, `.env.*`, `*.pem`, `*.key`, `credentials.json`, `.npmrc`, `id_rsa`, or `secrets/` file.
- Debugging auth, payments, or integrations — exactly when values are most likely to be pasted.
- Pasting command output: `env`, `printenv`, `docker inspect`, `kubectl get secret -o yaml`, `psql` output, `curl -v` (headers carry cookies and tokens), stack traces with connection strings.
- Quoting user records, test data, or anything copied from production.
- Screenshots, log excerpts, or PR descriptions pasted into memory.
- **Pasting any log line, error message, or URL that came from a live service.** A service's own
  error output can carry the credential that caused the error — this is the single most common
  way a real secret ends up in a memory file. The Telegram polling error
  (`…/bot<id>:<secret>/getUpdates…`) is the canonical example: the URL *is* the credential.
- **Any numeric id, chat id, account id, or user id** that appears in a log excerpt. Mask it
  unless it is genuinely public knowledge and stands alone with no credential attached.

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

### Mechanical check — do not skip this

The eye misses things. Run the live-secret grep before writing. It compares the draft against the
**actual** current values in the environment, so it catches fragments and composites that a
pattern-based read-through will not.

```bash
# From the repo root. Run AFTER writing the draft file, BEFORE staging it.
python3 - .ai/sessions/llm/<the-file-you-just-wrote>.md <<'PY'
import os, subprocess, sys

path = sys.argv[1]
blob = open(path, encoding='utf-8', errors='ignore').read()

def live(name, container):
    v = subprocess.run(['docker', 'exec', container, 'printenv', name],
                       capture_output=True, text=True).stdout.strip()
    return v

vals = {
    'TELEGRAM_TOKEN':       live('TELEGRAM_TOKEN', 'openclaw-bot'),
    'GITHUB_TOKEN':         live('GITHUB_TOKEN', 'openclaw-worker'),
    'AI_GATEWAY_API_KEY':   live('AI_GATEWAY_API_KEY', 'openclaw-worker'),
    'REDIS_PASSWORD_WORKER': live('REDIS_PASSWORD_WORKER', 'openclaw-worker'),
    'ALLOWED_USER':         live('ALLOWED_USER', 'openclaw-bot'),
}

def longest_fragment(val, blob):
    # Longest substring of val that appears in blob, across ALL start offsets.
    best = ''
    for i in range(len(val)):
        for j in range(len(val), i, -1):
            s = val[i:j]
            if s in blob:
                if len(s) > len(best):
                    best = s
                break
    return best

# Public format markers. These name a token *format* and carry no secret
# material, so prose may legitimately name them ("zero github_pat_ substring
# in stderr"). Only the secret portion after the marker counts as a leak.
PUBLIC_MARKERS = ('github_pat_', 'ghp_', 'gho_', 'ghu_', 'ghs_', 'sk-', 'sk-ant-')

def secret_portion(frag, val):
    # Strip any leading public marker from the fragment.
    for m in PUBLIC_MARKERS:
        if frag.startswith(m):
            return frag[len(m):]
    return frag

leaks = 0
for name, val in vals.items():
    if not val:
        continue
    if val in blob:
        print(f'LEAK: FULL {name} value present in {path}')
        leaks += 1
        continue
    frag = longest_fragment(val, blob)
    secret = secret_portion(frag, val)
    # 8+ chars of the actual secret = a leak.
    if len(secret) >= 8:
        print(f'LEAK: {name} fragment {frag!r} (secret chars: {len(secret)}) in {path}')
        leaks += 1

print('CLEAN' if not leaks else f'{leaks} leak(s)')
PY
```

Any `LEAK:` line means the file must be fixed before it is staged. A fragment of **8 or more**
characters of the secret is treated as a leak — see "Partial and composite secrets" above.

Three traps in this check, all of which produce **wrong results** if handled naively:

- **Do not break out of the search early.** A loop that stops at the first hit reports a 2-char
  match like `"git"` or `"be"` and floods the output with noise. The longest-match search must
  consider every start offset.
- **A public format marker is not credential material.** `github_pat_`, `ghp_`, and `sk-` are
  public format strings, and prose legitimately names them. Strip the marker, then measure only
  the secret portion. Comparing the fragment against the marker naively (e.g. "is this just the
  prefix?") is wrong — a fragment like `github_pat_` plus ten more characters is the marker
  **plus 10 secret characters** and is a genuine leak. Never use a real-looking credential in
  these examples; write the marker and a placeholder instead.
- **Check the whole tree, not just the file you edited.** A leak can sit in a file written
  several sessions ago.


### What to do when the check flags something

Mask it in the draft and re-run the check until it is clean. If the value is genuinely
non-sensitive (a public host, a placeholder), say so in the session file rather than silencing
the check.

## Before committing

- `git diff --cached .ai/` and read the added lines. Any raw credential or PII in the diff gets masked before commit, not after.
- Never `git add` a file you have not read for secrets.
- Do not use `git add -A` / `git commit -a` on a repo with `.ai/` active without reviewing the staged diff first.

## If you already leaked a value

First, **establish what actually leaked** — full credential, partial fragment, composite, or
non-secret id. The severity and the fix differ sharply, and over-rotating a public identifier is
as much a mistake as under-rotating a real key.

Measure it, do not guess:

```bash
# Is the FULL value in remote history?
TG=$(docker exec openclaw-bot printenv TELEGRAM_TOKEN 2>/dev/null)
git rev-list --all --remotes | while read c; do git grep -l "$TG" "$c" -- 2>/dev/null; done | sort -u

# What is the LONGEST fragment of the value present? (the substring sweep from above)
```

| What leaked | Severity | Correct action |
|---|---|---|
| **Full credential** | Compromise | Rotate immediately. History rewriting (`git filter-repo` + force-push) plus GitHub support for cached views is required, because rotation is the only fix that protects against already-cloned copies. |
| **Partial fragment** (any non-empty secret substring) | Reduce, not eliminate | Rotate if the fragment is long enough to narrow the search meaningfully (treat 8+ secret chars as enough). History rewriting is worth it if the fragment identifies the service or the account. |
| **Composite half** (e.g. the `bot_id` of a `bot_id:secret` pair) | Low, unless it stands alone | The secret half is what matters. If only the non-secret half leaked and it is genuinely public (a bot's own id is visible in its profile), rotation is usually unnecessary. Say so explicitly rather than reflexively rotating. |
| **A public id alone** (chat id, bot id, no secret attached) | Cosmetic | Mask going forward. No rotation. Do not rewrite history over it. |

Rules that hold in every case:

1. Stop. Say plainly in the session file: *which kind of value*, *which file*, *when*. Never
   re-quote the value itself.
2. Tell the user the severity **and** whether rotation is actually needed. Do not recommend
   rotation reflexively — rotating a credential that was never exposed adds operational churn and
   can break running services for no gain.
3. Mask the value in the file with a note that it was masked.
4. `.ai/` files are history records — never silently rewrite them to hide the incident. Leave the
   sanitized note.
5. History rewriting (`git filter-repo` + force-push) rewrites shared history. Only recommend it
   when the leak is a real credential, and always weigh it against the cost of a force-push the
   user did not ask for. Say plainly that masking a file afterwards does not clean history, and
   that rotation — not history rewriting — is what actually protects against a leaked secret.

## Scope

Applies to everything written into `.ai/sessions/`, `.ai/decisions/`, and any commit message or PR body produced by the agent. It does not replace the repo's real secret handling: keep secrets out of the codebase in the first place, with `.env` ignored, secrets from the environment, and a secret-scanning pre-commit hook. This skill is the last line of defense for memory, not the first.
