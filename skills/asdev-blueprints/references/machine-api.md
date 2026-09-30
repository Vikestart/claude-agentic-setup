# Machine API — platform contract
*Part of the `asdev-blueprints` skill. Tier 2. Read this before scaffolding, auditing, or building any of:
`mapi.credentials`, `mapi.gates`, `mapi.read`, `mapi.schema`, `mapi.work`, `mapi.test-accounts`,
`mapi.ip-allowlist`, `mapi.openapi-clients`.*

## Contents

[1 Scope and timing](#1-scope-and-timing) · [2 The contract](#2-the-contract):
[credentials](#21-mapicredentials--machine-identity) · [gates](#22-mapigates--kill-switch-flags-grants) ·
[read](#23-mapiread--the-table-allowlist) · [schema](#24-mapischema--proving-what-shipped) ·
[work](#25-mapiwork--governed-writes) · [test-accounts](#26-mapitest-accounts--disposable-users-non-production-only)
· [ip-allowlist](#27-mapiip-allowlist--binding-a-bearer-to-a-network) ·
[openapi-clients](#28-mapiopenapi-clients--contract-and-reference-clients) · [3 Invariants](#3-invariants) ·
[4 Reference implementations](#4-reference-implementations) · [5 Decision points](#5-decision-points) ·
[6 Gaps and design briefs](#6-gaps-and-design-briefs) · [7 Manifest rows](#7-manifest-rows)

Section 2 states the rules; **section 3 says why**, with the incident behind each — read both.
`asdev-conventions` owns HOW code is written, `asdev-web-audit` the scanners, the global `CLAUDE.md` planning
gates / `.docs/` layout / git / orchestration. Identity, admin RBAC and privacy/deletion have their own
reference files here, and this capability depends on all three.

## 1. Scope and timing

This lets an LLM — the owner's, or an agent acting for them — **read the schema and the non-sensitive tables
of staging AND production, and perform governed write work**, without a shell, a database password, or a
copy of production data on a dev box.

**Tier 2: before public launch, and specifically after the dev/staging/prod database split.** The moment
local stops sharing a database with production, "let me just check what production looks like" becomes
impossible — and the honest replacement is an authenticated, scoped, audited read API, not a re-pointed
`.env`. One project hit this exactly: the database split closed direct dev access to production data, and
the read API shipped in the phase straight after as the sanctioned replacement. A machine API built *before*
the split is just a second door into a database you were already reaching the wrong way. It is Tier 2 rather
than Tier 1 because it presumes what Tier 1 built: an admin panel with re-authentication, an append-only
audit log, an environment name the code can trust, and an erasure path. It is not optional-forever — the
alternative is shell access, which has no scopes, no allowlist, no revocation and no audit row.

Two halves, separable; ship the read half first. The **read half** (`mapi.credentials`, `mapi.gates`,
`mapi.read`, `mapi.schema`, `mapi.ip-allowlist`) answers "what is out there" — small, high value, low blast
radius. The **write half** (`mapi.work`, plus `mapi.test-accounts` on non-production) lets a model produce
content under server-side validation and human approval — large, and worth building only where
machine-generated content is genuinely part of the product. `mapi.openapi-clients` spans both and should
exist from the first route.

## 2. The contract

Architecture-agnostic. "Resource" means one addressable capability; whether it is reached as `GET
/api/v2/reads/{resource}` through a REST front controller or as an action name in a dispatch table is a
routing decision, not a contract decision. What is contractual is the shape: what is stored, what is
exposed, and what must be true before a request is served.

### 2.1 `mapi.credentials` — machine identity

**Data.** One credentials table: an indexed random **selector**; a **domain-separated hash of the
validator**; the **accountable actor** (a real user row, so the credential inherits that account's fate); a
label; the granted scope list; optional scoping axes (language, tenant); the actor's **session version and
MFA state at issuance**; `expires_at`; `revoked_at`; `last_used_at`; the optional address allowlist; and a
short **mutation-admission lease** (nonce + until) so one credential runs one mutation at a time and a
crashed request self-heals. Two grains, both legitimate: **operator-grade**, bound to an administrator and
acting as the owner's own machine identity, and **user-grade**, where any account mints personal tokens
acting as exactly that account.

**Surfaces.** Issue (bearer shown **once**, never re-fetchable, never in browser storage); revoke; edit
label/scoping/allowlist; a keyset-paged list showing metadata only, which the account-export path must
exhaust rather than truncating at page one. Every authority-changing action re-authenticates (password, and
MFA when enabled) and writes its own audit row.

**Behaviour.** Wire format `<prefix>_<selector>.<validator>`: the prefix identifies the credential kind at a
glance, the selector is an indexed lookup, the validator is compared with `hash_equals`. Every request
re-checks the actor (exists, still authorised, not locked, no pending deletion, session version and MFA
state unchanged since issuance). Revocation is a **tombstone**, never a `DELETE`. `last_used_at` is written
on mutations for free and on reads through a 5-minute throttle, so GET traffic does not become write
traffic.

**Credential names are contract.** The environment-variable name a credential is read from gets hardcoded
into reference clients and asserted by suites, so renaming it to tidy it up breaks every client at once.
Name them per environment and never reuse one name across two — a production name and a distinct staging
name; where one machine also holds credentials for *remote* environments, keep the name for this machine's
own endpoint separate from the remote ones, and keep the remote ones in the local `.env` only. Pick names
once, blank keys into `.env.example`, treat a rename as breaking. **The broker pattern**: one durable,
human-issued credential per environment that can mint *temporary* subordinate credentials or accounts on
non-production — the staging credential mints test accounts through the mint route. A credential may
**never** mint or revoke credentials of its own kind.

### 2.2 `mapi.gates` — kill switch, flags, grants

**Data.** Settings rows, one per lever: a single **global kill switch**; one flag per read resource; **two**
per work resource (claim and commit, separately); and a flag for anything whose availability is a deployment
decision. Plus a **grants** table — `(credential, resource, kind, role, scope-axis)` with a scope list and
`revoked_at`, under a unique key on the exact tuple.

**Surfaces.** An admin Gates tab (platform-wide flag matrix) and a Grants tab (per-credential toggle matrix);
both are authority changes needing re-authentication, CSRF and one audit row per toggle.

**Behaviour.** The kill switch is read **first, on every request, before authentication** and before any
other refusal; off means one stable documented code with `Retry-After`, identical for every route. Grants
are deny-by-default and matched **exactly** — resource + kind + role + scope axis + scope — with no wildcard
except a reserved sentinel for resources that declare themselves non-scoped, and that sentinel must be
unreachable from the wire. Flag consistency is enforced server-side, not in the UI: commit cannot be enabled
while claim is off, and a dependent flag cannot be enabled where the feature would refuse to act anyway,
while **turning anything OFF is always allowed, from anywhere** — the documented instant rollback. Grant
batching is read-kind only; write authority stays strictly per resource. Refusals are distinguishable and
stable: global kill switch, resource disabled, commit disabled, insufficient scope and invalid credential
are five different codes, and client diagnostics depend on telling them apart.

### 2.3 `mapi.read` — the table allowlist

**Data.** A **committed machine-readable policy file** the code loads and proves at startup. Per table: a
tier (`open` / `limited` / `blocked`), a mandatory free-text **reason**, projected columns with type +
nullability + max length, for `limited` tables the **blocked columns and why**, declared filters with
operators, the keyset order key, and a per-table row cap. Plus global bounds (default and ceiling page size,
response byte cap, cursor byte cap) and a published tier-count summary the validator checks against the
entries.

**Surfaces.** One read resource per table, plus a `count` view. Query contract: `view`, `limit`, `cursor`,
`filter.<column>` (exact dotted names). Each table has its own flag and its own grant.

**Behaviour.** **Allowlist, never denylist** — a table absent from the file is unreadable, and adding a
table to the schema does not add it to the API. `users` and every credential, session, secret, token,
password-reset, support and behavioural table are **blocked outright**; expect the blocked tier to be large,
a third to a half of a real schema, and treat that as the feature working. `users` serves an unfiltered row
count and nothing else, and only because a verification client needs to know whether it is reasoning about 2
rows or 2,000. **A count-only resource accepts no parameters at all**, refused before any SQL is built. The
projection is column-level and a filter may only name a projected column. Paging is keyset, a nullable
column may not anchor it, and the maximum cursor length is **derived** from the order key's declared widths
and checked against the published bound. Settings-shaped tables add a key-level allowlist: allowed prefixes,
allowed exact keys, a denied-exact list, and a deny pattern over
`secret|token|password|api_key|credential|private_key`. Responses are `Cache-Control: no-store, private`,
and read ETags serve `If-None-Match` caching only, never a mutation precondition.

### 2.4 `mapi.schema` — proving what shipped

**Data.** None of its own: `information_schema` plus the migration ledger. **Surfaces.** One scope-gated,
GET-only, **parameterless** resource. Two shapes are in service. **Names + verdict**: live table count, live
table names, the read policy's version, and an agreement verdict naming missing and extra tables — no
columns, no rows, justified because the published contract already names every table. **Full structure +
fingerprint**: columns with type/nullability/default/extra, indexes with uniqueness/type/prefix length,
table engine and collation, foreign keys **with referential actions**, a `fingerprint` over exactly those
four dimensions, and the migration ledger of filenames, checksums and applied/pending/drifted counts.

**Behaviour.** Structurally incapable of returning application rows — no request parameter reaches a query —
so the credential cannot be widened into data access without new code. Disabled by default (blank or
too-short token ⇒ 404), and a wrong credential gets the same 404 as a disabled endpoint, so probing cannot
confirm the route exists. State what the fingerprint covers: two schemas sharing one agree on those
dimensions, not on everything.

**Proving a migration ran in production from a dev box.** The version endpoint is *not* evidence — the
deploy publishes files before it runs the migration. Have the migration runner write a settings row (`{at,
version, seconds, host}`) **after** the migration returns, allowlist that one key for reads, and **poll** it
until it names the release you deployed. One project measured 27 s, 94 s, 178 s and one past 5 minutes across
four consecutive deploys — all queue and lock, none of it the migration — and back-to-back deploys
serialize. Allow ten minutes: a single read inside that window is indistinguishable from a real failure, and
produced a confident, wrong verdict once already.

### 2.5 `mapi.work` — governed writes

**Data.** Seven concepts, whatever they are called:

| Concept | Holds | Key constraint |
|---|---|---|
| **order** | what work is wanted: resource, scope, target count, selector | one open order per (topology, resource, scope, selector) — a unique overlap slot |
| **workflow** | one attempt at an order | one active workflow per order |
| **stage** | a step inside a workflow, with its state hash and provenance | a source receipt seeds exactly one stage |
| **claim** | a lease over selected units | one active claim per credential, and one per subject slot |
| **idempotency** | key hash + request hash + stored response projection | unique per (credential, environment, operation, key hash) |
| **receipt** | the immutable record that a commit happened | unique per claim, and per (environment, outcome) and (environment, packet) |
| **review queue** | the validated writer payload awaiting a human | unique per receipt |

Every row is **environment-scoped** by an id folding the app's base URL and database name, so an order
created in one environment is invisible in another.

**Surfaces.** Discovery (`resources` — only what this credential is granted, with the *effective* flag
state; `targets` — what work exists), order listing, workflow create/propose/cancel, claim
create/heartbeat/validate/commit/cancel. **Orders are created by an operator in the admin panel of the
environment that will lease them**, never by the client: an order describes work rather than granting power,
so it needs no re-authentication, but it does need a human to have asked for it.

**Behaviour.**
- State machine `leased → validated → committed`, with `cancelled`, `expired`, `superseded` terminal.
  Partition the state space with `IN` / `NOT IN` so an unknown future state lands in history rather than
  vanishing from a listing.
- Leases: 30 min initially, +15 per heartbeat, hard cap 120. **The database clock is authoritative**;
  responses carry the DB expiry plus derived remaining-seconds and client clocks are display-only.
  Heartbeats get their own rate lane, so an exhausted mutation window cannot kill a live claim.
- Every mutation needs an idempotency key, minted **per method invocation** and replayed across that
  invocation's retries, and a **byte-exact strong ETag precondition**.
- Validation runs the server's real canonical writer inside a transaction it rolls back, records a
  deterministic reply digest plus bounded counters, increments the revision and returns a new ETag. Commit
  resends the full reply, must match that digest and present that ETag, and is **one transaction**: domain
  rows, receipt, run log, claim compare-and-swap and audit event together.
- Retention: terminal claims 90 days, events 180, idempotency 24 h, rate windows days. Prune on a cron
  worker, never on the request path.
- **Machine-produced content is DRAFT-ONLY** (a standing product directive; no toggle, no exception). A
  commit stores the *validated writer payload* in a review queue and writes no domain row; the admin
  approves it through the **same writer**, or rejects it. The machine contract does not move — claim →
  validate → commit → receipt is byte-identical from the client's side — and a rejection never refunds the
  receipt. Approval replays against **current** state and may legitimately refuse; a rejected draft's retry
  must present a fresh identity, and "revise" creates a NEW pending row rather than flipping a rejected one
  back to pending. ⚠️ Intercepting the machine API does not intercept the product — census the panel, worker
  and CLI twins too (invariant 17). Where a commit path makes provider calls of its own (a QA/repair gate),
  **record them at draft time and replay them at approval**.
- Publish a **coverage ledger**: one row per surveyed machine-work seam, a closed classification vocabulary,
  and a mandatory note on every row deliberately not externalized (one project's ledger: 56 surfaces, six
  classifications, shape enforced by a suite). Without it a seam can be quietly left out and nobody can
  tell.

### 2.6 `mapi.test-accounts` — disposable users, non-production only

**Data.** No new columns if the identity model already has `is_test_account`, an account origin and a
scheduled-deletion timestamp. Reuse the existing expiry field: a second one creates two answers to "when
does this account die".

**Surfaces.** One mint route. Required fields include the address allowlist plus whatever the identity model
cannot default — a field with no sensible default is required rather than guessed, and its absence is a 422.
Everything privilege-shaped that is not `role` — `role_id`, `is_admin`, `is_test_account`, `username` — is
**refused with 422, never ignored**. ⚠️ A closed allowlist vets key NAMES only: a `role` of the wrong *type*
(`1`, `true`, `["admin"]`) sails through it, so check the value's type at both the endpoint and the writer,
and keep the two normalizations identical.

**Behaviour — five gates, in order:**
1. **Environment**, fail-closed: `staging` or `local` only. An unset or unrecognised environment name also
   refuses — "I could not tell where I am" must never resolve to "go ahead". Checked first, so production
   answers as it would for a path it does not implement.
2. **Global kill switch**, checked explicitly in the handler — defence in depth for direct in-process
   callers, since this route has no resource or grant to check authority against.
3. **A feature flag**, off by default, so reaching this on staging is two deliberate acts.
4. **A second flag for administrator accounts**, which grants nothing unless gate 3 is on.
5. **A floor inside the provisioning writer**, which holds for a caller that never read the endpoint.

Separate ceilings per role (say 50 ordinary accounts, 3 administrators) and per-role lifetimes (72 h / 8 h)
under an absolute writer-side cap (14 days — deliberately *longer* than the endpoint maxima, because capping
at the writer without keeping the per-role maxima would widen the API). **The ceiling refuses rather than
making room.** The password is returned **once**, stored as a hash, logged nowhere, and absent from the
durable who-minted-what audit row (that row outlives the account). Expiry locks the account out immediately;
**erasure does not fire by itself** — run a sweep scoped to `is_test_account = 1 AND origin = api`, so it
can never reach a real user inside their deletion grace window, through the project's one audited erasure
path. The account **type is immutable**: no action may flip an account into or out of test status — flipping
in produces a test account with no expiry and no binding, flipping out strips the binding off one that had
it, so the replacement is to create a new account — asserted by a codebase sweep, not a code review.

### 2.7 `mapi.ip-allowlist` — binding a bearer to a network

**Data.** One nullable JSON column per credential (and, where test accounts exist, per user). NULL and `[]`
both mean **unrestricted** — what every pre-existing row is, and what makes the feature purely additive.
**Behaviour.** One matcher, one stored format, shared by credentials and accounts. Entries are canonicalized
**at write** (IPv6 case and zero-compression collapsed, IPv4-mapped IPv6 reduced to IPv4, duplicates
dropped), and anything with two readings is **refused with the corrected form suggested** rather than
silently repaired — a CIDR with host bits set is the common one. Matching is binary and family-aware. A
corrupt stored value returns a sentinel that is not an address and therefore matches nothing: **fail
closed**. Enforce it the instant the bearer matches and **before** grants are read, the actor row is locked
or a rate window is advanced; for accounts, enforce at login **and on every authenticated request**, so an
exported session cookie is not a way around it.

⚠️ **The address is `REMOTE_ADDR` and nothing else.** `X-Forwarded-For`, `X-Real-IP` and `Forwarded` are
client-settable. Behind a reverse proxy `REMOTE_ADDR` is the proxy, so an allowlist there can only say "the
proxy", which allows everyone — detect that honestly (a loopback peer *plus* a forwarding header proves
something in front dropped the real peer), warn once per process into the audit log, show it in the panel,
and fix it with `real_ip` / `mod_remoteip`, never by trusting the header.

### 2.8 `mapi.openapi-clients` — contract and reference clients

**The OpenAPI document is the source of truth** for routes, shapes and operation ids, and lives in the
repository next to the code. It is deliberately exempt from the deny rules that hide `/scripts/`,
`/includes/` and `/clients/` from HTTP: it is the public contract, and production serves it.

**Reference clients** — a CLI for operators and an MCP server for model harnesses — share **one transport
module**. Five load-bearing properties: **thin** (no prompt construction, no reply validation, no database,
no authority decisions — a rule a client would need belongs on the server); **one tool per `operationId`**,
generated from the spec with local `$ref`s inlined and a conformance suite asserting set equality both ways
(an MCP-only convenience tool is authority with no REST equivalent and no audit trail); **secrets never
leave the environment** — not into argv (other users read `/proc` and `Get-CimInstance Win32_Process`),
files, logs or exception text — behind one redaction boundary every output path goes through; **dry-run by
default**, writing behind two explicit flags plus `confirm: true` on the MCP tool, so forgetting one yields
the safe posture; and **exact wire names**, dotted filters included, URL-encoded rather than translated.

Transport: HTTPS required (loopback excepted); the base URL is an origin and nothing more; **redirects are
an error, never a hop** (a redirect forwards the credential to a host the caller did not choose, and a 302
turns a POST into a GET while keeping the header); retry only `429` and `503`, honouring `Retry-After` to a
30 s cap and surfacing anything longer; `409`/`412`/`422` are semantic outcomes, never retried.

⚠️ **The `Authorization`-header defect and its two-layer fix.** Apache withholds `Authorization` from the
CGI environment, so a bearer sent that way silently disappears and **every** credential is rejected over
real HTTP while hermetic suites stay green (they call the resolver with a synthetic `$_SERVER`). Fix it in
both layers and keep both: the server republishes the header in `.htaccess` *and* falls back to
`apache_request_headers()`; the client offers an alternative header name (something vendor-neutral such as
`X-Api-Token`, documented as the primary transport for exactly this reason). Assert both, including that the
rewrite rule still exists. The same class of defect hit conditional headers — a compressing production edge
dropped or weak-wrapped `ETag` — so the ETag is carried in **both** header and body, the precondition is sent
as `If-Match` **and** a vendor header, and any disagreement beyond the one measured weak-wrapper shape fails
closed rather than guessing.

Ship a `doctor` command: the server answers every authentication failure with one identical problem document
(correct — it must not reveal whether a token exists), which makes debugging opaque, so `doctor` splits what
the client can verify locally (unset variable, wrong shape or length) from what only the server knows
(revoked, expired, actor no longer authorised, session version or MFA changed) — and never guesses.

## 3. Invariants

1. **Store only a domain-separated hash of the secret; show the raw value once.** Hash
   `prefix\0selector\0validator` with SHA-256 and compare with `hash_equals`; storing the digest plus a dozen
   cleartext characters purely to identify the row is fine, storing more never is. Domain separation stops a
   digest from one credential system being replayed into another that hashes the same way.
2. **Revocation is a tombstone, never a delete**: a deleted row lets the same digest be re-minted and
   destroys the audit trail. Put the ownership predicate *inside* the UPDATE — a check and a write that are
   two statements are two statements a later edit can separate.
3. **A credential can never mint or revoke credentials.** Otherwise a leaked token mints its own replacement
   and can lock the owner out of their own account.
4. **A credential is worthless outside its environment, and the environments use different credential
   NAMES.** A shared name is how a "staging is on the production database" finding was once *proven* — that
   test only worked because the two environments' credentials were identical. Distinct names mean a
   credential aimed at the wrong environment fails loudly instead of quietly working.
5. **Every request re-checks the accountable actor, and the lookup fails closed.** Compare the actor's
   session version and MFA state against the values recorded at issuance, so a password change, MFA change,
   role demotion, lock or deletion revokes machine access without anyone remembering to. Refuse a credential
   whose account is not `active` inside `resolve()` rather than in each caller, and deny on a database error
   instead of falling through to "grant".
6. **The kill switch is read FIRST, before authentication and before any other refusal.** One project learned
   this on its public surface: the feature's own refusal arm ran before the switch was consulted, so a
   deployment with the feature OFF answered 404 where the right answer was "this installation does not have
   that feature". Staging caught it and local could not, because staging ships dark while the local switch
   was on. When a feature is off, the deployment must answer as if it had never been built.
7. **Turning a gate OFF is always allowed; turning one ON may be refused.** Do not let an operator enable a
   flag where the environment would refuse to act anyway, because a stored `1` that reads like a live
   capability is worse than an absent row. Rollback must never be blocked by a consistency rule.
8. **The read policy is an allowlist in a committed machine-readable file the code loads and proves.**
   Validate it at load — identifiers re-matched against a regex, unexplained classifications refused,
   published tier counts compared against the entries — and raise rather than degrading to a default,
   because the one thing it may never do is let a table inherit access it was not given. ⚠️ The enforced
   file, not a document, is the allowlist: prose summarising a policy drifts from it, and a live one has
   already drifted by a whole table and one tier count. Where the two disagree the file is right — better
   still, generate the prose from the file.
9. **`users` and every credential/session/secret table are blocked outright; everything else is
   column-limited with a written reason.** A `limited` entry names its blocked columns *and* why. An admin
   change log's before/after value columns are the standard case: arbitrary TEXT can hold any value an admin
   ever changed — including a setting this same policy blocks at the key level.
10. **A resource that serves a count may not serve a filter.** A filtered count over unreadable rows is a
    bit-at-a-time extraction oracle. Enforce this in the policy validator *and* refuse every parameter before
    SQL is built, rather than relying on which filters were declared.
11. **A missing key proves nothing.** Where a settings-shaped table is key-allowlisted, a full page walk
    that does not find a key is not evidence the row is absent. One investigation walked every readable row,
    found no row with the expected prefix, and the settings were in fact present — behind the key allowlist.
    Say so wherever the read path is documented, or someone will conclude a deploy failed.
12. **The schema resource must be structurally incapable of returning rows** — no request parameter reaches
    a query, the response shape is fixed, it is GET-only. That is what makes the token mean "see how this
    database is SHAPED" and nothing more. One was written after a schema question cost a full day on
    production.
13. **One clock, and it is the database's.** Expiry is written and read with `CURRENT_TIMESTAMP`; a caller
    passes a *lifetime*, never a timestamp. Three clock-mixing defects shipped in one project's expiry paths
    alone — the test-account sweep, the session access state, the expiry computation — and where PHP and
    MySQL clocks disagree by more than the lifetime an account is past due at birth: locked out on its first
    request, erased by the next mint. A suite measuring expiry with PHP's `time()` asks the clock that wrote
    the value whether it agrees with itself, and passes on the broken box.
14. **Uniqueness must agree with the lookup.** Receipt keys that are global while every reconciliation query
    filters by environment mean one environment's commit makes the other's lookup miss and then hit a raw
    duplicate-key error instead of the contracted conflict.
15. **Machine-produced content never goes live without a human approving it — no toggle, no exception** (a
    standing product directive). The queue is a *layer before* the domain, not a filter over it: a drafted
    commit writes no domain row at all, and approval replays the existing writer. Delete any per-resource
    "draft mode" setting rather than defaulting it, because a lever that can be turned off is the exception
    the directive forbids.
16. **A commit path that calls a provider must record those calls at draft time and replay them at
    approval.** One project found a QA gate issuing fresh model calls at draft time *and* at approval, so the
    approved item could differ, in every block the second pass touched, from the run a human decided on —
    while the approval silently spent tokens. A null reply must be recorded and served as a null: a failed
    call is a normal terminal state, and dropping it leaves the replay one reply short, making legitimate
    drafts unapprovable.
17. **Intercepting the machine API does not intercept the product.** Census the twins before you trust
    the interception: expect nearly every intercepted machine resource to have an admin-panel twin
    writing live. Route each twin through the same queue under the machine twin's resource key plus a
    mode discriminator — a *new* key resolves to "not interceptable" and arms nothing, silently.
18. **The idempotency key is per method invocation, replayed across that invocation's retries.** A
    body-derived scheme broke when a long-lived MCP process reusing one client made two *distinct* operations
    with identical bodies share a key: the server replayed a stored projection, so the second operation
    received a stale, possibly cancelled result forever. Duplicate-write safety across invocations belongs to
    the server's state machine.
19. **The idempotency replay store must not persist a secret.** A standard store persists the response body,
    and on a mint route that body carries the plaintext password exactly once. Accepting `Idempotency-Key`
    and deliberately *ignoring* it is a defensible answer, provided the consequence is documented rather than
    hidden — a retry after an ambiguous timeout mints a second account. Decide this deliberately for any
    route whose response carries a one-time secret.
20. **The address is `REMOTE_ADDR`, never a forwarding header, and both families must be named.** Where the
    caller reaches the box over a private overlay network, `REMOTE_ADDR` is that network's address and the
    client may well arrive over IPv6 — an IPv4-only allowlist, even `0.0.0.0/0`, then refuses every login,
    because the matcher compares binary lengths and a family mismatch looks exactly like a wrong address.
21. **Test accounts are non-production by construction, and the last gate lives in the writer.** Four gates
    a caller can read and one it cannot. The writer-side floor holds for a future caller who never read the
    endpoint — and must be tested *through the writer*, because the endpoint refuses first and made the
    writer's own check vacuous on the first attempt.
22. **Assert the deployment-shaped defences, not only the logic.** The `Authorization` rewrite rule, the
    deny directives, the session-free route listing and the CSRF-exempt-plus-header-only-auth pairing are
    security controls a hermetic suite cannot see failing. Assert that the `.htaccess` rule still exists, and
    that a valid session *alone* gets 401 on the machine route, so a future convenience edit ("let logged-in
    users try it from the browser") fails loudly rather than quietly opening it.
23. **A JSON-RPC notification does the work; it just gets no reply.** One implementation returned 204 before
    dispatching anything without an `id`, so a mutating tool call sent as a notification was silently
    discarded — the caller saw success and nothing happened. Read the flag inside the single reply/fail
    funnel, so unimplemented notifications are still answered silently rather than with an error, which
    would be the same violation in the other direction.

## 4. Reference implementations

*Pointers into the author's own repositories live in the optional `local/pointers/machine-api.md` overlay,
which is not shared. The contract in §2 and the invariants in §3 stand on their own: they say what to
build and why, not where one team's copy happens to sit.*

## 5. Decision points

| Decision | Options | Default |
|---|---|---|
| Credential grain | operator-only vs per-user tokens | **Operator-only.** Per-user tokens are a product feature; add them when users ask to automate their own account. |
| How much to build | read + schema; or add work orders | **Read + schema.** Build `mapi.work` only where machine-generated content is part of the product. |
| Schema resource shape | names + verdict; full structure + fingerprint | **Full structure + fingerprint.** Answers more, no more dangerous — neither shape can return a row. |
| Token transport header | `Authorization: Bearer` only; or an alternative | **Both**, with the alternative documented as primary. The Apache defect is silent and total. |
| Read policy granularity | table tiers; per-column only | **Tiers + per-column allowlist.** The tier makes "blocked" auditable at a glance. |
| Who creates work orders | operator in the admin panel; the client | **Operator, in the environment that will lease it.** An order created elsewhere is invisible and holds an overlap slot. |
| Draft-only enforcement | always; per-resource flag | **Always.** A standing product directive; a flag is the exception it forbids. |
| Test accounts | build; skip | **Build on staging only**, once agents need signup/session-gated flows. Never on production. |
| IP allowlist | optional; mandatory | **Optional for credentials, mandatory for test accounts.** Behind an unconfigured proxy a mandatory allowlist locks everyone out — safe, but rarely wanted. |
| Client surfaces | CLI; MCP; both | **Both, over one transport module.** They diverge the moment they have two HTTP paths. |
| MCP transport | stdio; HTTPS POST | **HTTPS POST** when the server is already public; **stdio** when the client must hold a local credential. |

## 6. Gaps and design briefs

- **A route that exists on the server but not in the contract.** ⚠️ A conformance suite that generates one
  tool per `operationId` and asserts set equality both ways is an oracle only over what the spec lists: a
  dispatchable route the spec omits passes that assertion *because* it is missing, and the newest route is
  then exactly the one no client can call. Make "the spec names every dispatchable route" its own assertion,
  derived from the dispatch table. **No reference implementation yet** — write it with the dispatcher.
- **Idempotency on a route whose response carries a one-time secret. No reference implementation yet.** The
  shape is a replay record storing the *non-secret* projection plus a success marker, so a retry answers
  "already done" without the password. Until it exists, document such a route as "a timeout means
  may-or-may-not".
- **A per-credential capability that is not a grant. No reference implementation yet.** A route with no
  resource, scope axis or role to hang a grant on is authorised by nothing but a valid credential and a flag,
  so on a permitted deployment *any* credential can call it, including a read-only one. The fix is a
  resource-less capability column on the credential row, not a fake grant.
- **A cron-driven expiry sweep. No reference implementation yet.** A sweep that runs on the mint path only
  leaves an idle box holding its last lapsed rows — locked out, not erased.
- **One rate budget across the human and machine surfaces. No reference implementation yet.** Metering the
  machine API separately from the human one (per credential and route class, or per token hash and per IP)
  is the usual state; a single shared budget is unexplored.
- **A machine API on a modular CMS.** A module system wants per-module read-policy contributions rather than
  one central file. Unexplored.

## 7. Manifest rows

| Capability | Tier | Done means |
|---|---|---|
| `mapi.credentials` | 2 | Credentials are hashed at rest, shown once, per-environment, scoped, revocable by tombstone, with `last_used_at` tracking; every request re-checks the accountable actor; no credential can mint or revoke a credential; the credential names are in `.env.example` and in the client. |
| `mapi.gates` | 2 | A global kill switch is read before authentication on every request; per-resource flags and per-credential grants exist with deny-by-default exact matching; the admin panel toggles them behind re-authentication with one audit row each; turning anything off always works; refusals are distinguishable, stable codes. |
| `mapi.read` | 2 | A committed policy file the code loads and proves lists every readable table with a reason, a per-table column allowlist and declared filters; `users` and every credential/secret/session table are blocked; count-only resources accept no parameters; paging is keyset with a derived cursor bound; the enforced file — not a document — is the allowlist. |
| `mapi.schema` | 2 | A scope-gated, parameterless, GET-only resource reports tables/columns/indexes/foreign keys (or names + verdict), a fingerprint and the migration ledger, and cannot return an application row; a dev box can prove a production migration ran by polling a marker written after the migration returns. |
| `mapi.work` | 2 | Order → workflow → claim → validate → commit works end to end with DB-clock leases, per-invocation idempotency, ETag preconditions, a one-transaction commit with a unique receipt, and retention; every machine commit lands in a human review queue that replays the same writer on approval, with no toggle; a coverage ledger names every machine-work seam. |
| `mapi.test-accounts` | 2 | One mint route, refused on production by five independent gates the last of which lives in the provisioning writer; accounts are expiring, address-bound, type-immutable, origin-tracked and ceiling-limited per role, and are swept through the audited erasure path; the password is returned once and never stored or logged. |
| `mapi.ip-allowlist` | 2 | One CIDR-aware v4+v6 matcher and one stored format shared by credentials and accounts; enforced immediately after the bearer matches and, for accounts, on every request; `REMOTE_ADDR` only, with proxy masking detected and surfaced; corrupt values fail closed; both address families named in the staging allowlist. |
| `mapi.openapi-clients` | 2 | An OpenAPI document in the repo is the source of truth and names every dispatchable route; a CLI and an MCP client share one transport module, are thin, read secrets from the environment only, default to dry-run, and carry the two-layer `Authorization`/ETag defences; `doctor` separates local from server-side auth failures; client source is unreachable over HTTP while the spec is deliberately served. |
