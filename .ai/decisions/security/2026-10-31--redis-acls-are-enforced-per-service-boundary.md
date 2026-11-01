# Redis per-service ACLs are the datastore boundary and must be exercised against a live server

- **Date:** 2026-10-31
- **Decided by:** opencode (company-coder), implementing the confirmed baseline in
  `.ai/decisions/security/2026-10-28--no-api-keys-in-frontend-rls-in-database.md`
- **Topic:** security

## Decision

Redis access control in this repo is a real security boundary, not configuration hygiene. It is
enforced in two dimensions at once, and both dimensions must be correct for a service to work:

1. **Key scope** — each service may only touch the key namespaces it owns. The bot owns chat,
   queue, job, jobs, rate, and worker keys. The worker owns chat, queue, job, jobs, and worker
   keys. The ML service owns the ML state keys. The dashboard API owns the ML state keys it reads
   and nothing else.
2. **Command scope** — read-only services are limited to the commands they actually need, not to
   a generous list of plausible ones. The dashboard API is read-only and is limited to reading
   values and lists plus a connectivity ping. It cannot write, and it cannot run hash, set, or
   sorted-set commands.

The access rules are also interpreted the way Redis actually interprets them, which means the
order of the rules is load-bearing: a blanket deny placed after the individual grants cancels
them, and the resulting user can do nothing at all. The deny comes first, then the grants.

## Why

The earlier decision already established that a single shared Redis password is a blast-radius
problem and that per-service ACLs with key-pattern permissions are the Redis equivalent of
row-level security. The README and PRD both describe per-service ACLs as the current design. The
templates did not actually deliver that: the rules were wrong in three separate ways at once, and
because the ACL file is only read when Redis starts, none of the defects were visible until the
containers were actually brought up.

The concrete failure was not a subtle leak. It was a total denial of service, and it presented to
a reader as a dashboard application bug — error responses from routes whose logic was correct.
The opposite failure mode is worse and was avoided by inspection: had the command scope been left
broad on a service that was supposed to be read-only, the boundary would have looked healthy while
providing no isolation at all.

The general lesson is that a permission boundary expressed as configuration is only real once it
has been tested against the running system from the position of each service. Reading the
template cannot substitute for that. A rule that looks right and a rule that behaves right are
different things, and only the second one counts as enforced.

## What stays

- The dashboard API stays read-only, and its command scope stays minimal rather than being
  widened for convenience. Convenience is what turns a read-only service into a write-capable
  one.
- Services that genuinely need read-write access to their own namespaces keep it. The point is
  per-service scoping, not uniform restriction.
- The Redis datastore stays isolated from the network, with no anonymous access and no shared
  administrator password.

## What changes

- New rule: an ACL change is not complete until every service has been exercised against the
  live Redis using its own credentials, covering both the operations it needs and at least one it
  must be denied.
- New rule: when a service's real key and command usage is audited, the audit compares the
  code's literal key names and Redis calls against the template, rather than assuming the
  template is right.
- New rule: a Redis ACL change requires a container restart to take effect and is verified after
  that restart, not before.

## Supersedes / relates to

- `.ai/decisions/security/2026-10-28--no-api-keys-in-frontend-rls-in-database.md` — this decision
  completes the per-service Redis ACL split that the earlier decision deferred as future work.
  The earlier file's statement that Redis uses a single shared password describes the state before
  the split; that part is now superseded, and its general principle is unchanged.
- `.ai/decisions/llm/2026-10-31--bot-as-scoped-gateway-consumer-with-contract.md` — the same
  least-authority principle applied to the gateway credential, where a scoped virtual key replaced
  an administrator key. The Redis ACLs are the same idea applied inside this repo.
