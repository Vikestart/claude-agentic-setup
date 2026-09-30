# Privacy and legal — platform contract

*Part of the `asdev-blueprints` skill. Tier 1. Read this before scaffolding, auditing, or building any of: `privacy.consent`, `privacy.export`, `privacy.deletion`, `privacy.retention`, `legal.pages`, `legal.reconciliation`.*

## Contents

1. Scope and timing · 2. The contract (consent · export · deletion · retention · legal pages · reconciliation)
· 3. Invariants · 4. Reference implementations · 5. Decision points · 6. Gaps and design briefs · 7. Manifest rows

## 1. Scope and timing

Tier 1: **before the first real user**, not before launch. The moment one person who is not you has an account, you are a
data controller with statutory obligations that no amount of later engineering makes cheaper. Three reasons this cannot
slip to Tier 2:

- **The export inventory must be built while the schema is small.** It is a hand-classified list of every column that
  points at a person. At 20 tables that is an hour; at 90 tables it is a phase — and at that size it typically finds
  several tables that had been surviving "permanent" deletions for years.
- **Deletion is not a `DELETE`.** It is a state machine with a grace window, a verification step and a legal hold.
  Retrofitting it means auditing every write path that ever ran.
- **Payment providers read your legal pages during merchant review.** A merchant of record's domain verification loads
  `/terms`, `/privacy` and `/refund` with a crawler that does not run JavaScript. If billing (Tier 3) is anywhere on the
  roadmap, the legal set is on the critical path long before the first checkout.

Out of scope here: pricing copy ([billing.md](billing.md)), auth/session/rate-limit mechanics (`identity.md`), the admin
audit log and admin views of this data (`admin.md`), notification delivery (`notifications.md`), support-ticket storage
(`support.md`). Code style is `asdev-conventions`; planning gates, `.docs/` layout and deploy topology are the global
`CLAUDE.md`'s.

## 2. The contract

Architecture-agnostic. "Endpoint" means a routable action in whatever shape the project uses — a REST path, an action key
in a POST body, a CMS admin action.

### 2.1 `privacy.consent`

**Data.** A consent record with three fields minimum: the choice, the timestamp, and the **version of the policy that was
consented to**. For an anonymous visitor this lives in a first-party cookie (plus a localStorage mirror for continuity
across a cookie clear). For a signed-in user it additionally lives in a server row keyed by user id, so the choice
survives a new device, appears in the export, and can be proved.

**Surfaces.** A banner on every page until answered, whose buttons are a real `<form method="post">`; the server sets the
cookie and answers **303 See Other** back to the same path, so a reload cannot resubmit. With JS on, the client cancels
the submit and hides the banner in place. The privacy page carries a way to change the answer.

**Behaviour.**
- Two categories minimum: **strictly necessary** (session cookie, CSRF token, the consent record itself, a remember-me
  cookie the user explicitly asked for) and **consented** (everything else). Necessary cookies are disclosed, not asked about.
- **Make the honest answer the default: choose cookieless analytics.** If first-party analytics stores only
  `(day, path, referrer_host, count)` with no identifier, no IP and no cookie, there is nothing non-essential to gate and
  the banner becomes a disclosure rather than a lie.
- The banner **ships visible in the server-rendered HTML** and is hidden once answered — never revealed by JS after boot.
- Every storage access is individually wrapped: a browser with storage blocked must not throw.
- A policy version bump re-shows the banner for anyone whose stored version is older.

### 2.2 `privacy.export`

**One inventory, read by both export and deletion.** This is the most important structural rule in this file. The classic
GDPR defect is two hand-written lists — one for "what we hand back", one for "what we erase" — that drift, so a table is
exported but never deleted, or deleted but never disclosed.

**Data (in concept).**
- `ERASE_TABLES` — table → the column(s) meaning "this row is that person's data". **Explicit, never introspected.** A
  `user_id` column does not always mean ownership: an admin-action log's `user_id` is the acting administrator, a job
  queue's `created_by` is whoever queued it. A `DELETE` derived from a schema scan eventually finds one of those.
- `EXPORT_COVERAGE` — the same keys, each mapped to the named export dataset(s) carrying them. A runtime assertion
  compares the two key sets and **throws** on any difference.
- `USER_REFERENCE_COVERAGE` — every `(table, column)` in the live schema pointing at a person, mapped either to a
  subject-scoped safe dataset or to an explicit `@internal_operational` exclusion marker. Discovery for this check **is**
  introspective (real foreign keys to the user table, unioned with this codebase's actor-column names), and an
  unclassified reference refuses the download rather than silently omitting data. Scanning may introspect; deleting may not.
- **The same closed-registry mechanism extends to per-user record *kinds*, not just tables.** Where a notification system
  declares a closed list of admin-only kinds, the export declares a fixed safe projection for each of them, and one
  assertion compares the two sorted key sets and throws. Admin-only kinds are deliberately *not* exported verbatim — a
  privileged notification's copy can describe another person or a privileged target — so each is replaced by fixed
  generic text. Adding a kind therefore forces a decision about its export and erasure treatment; it cannot be forgotten.

**Surfaces.** One authenticated action streaming a machine-readable document (JSON), plus whatever admin view `admin.md` owns.

**Behaviour.**
- **Password re-authentication at the boundary**, on top of session + CSRF. A bulk PII dump must not be reachable from a
  merely hijacked session — the same gate as deletion. The subject id comes from the **session, never from input**.
- **Preflight before the first byte:** run every query with an impossible subject id and assert the coverage policy, so a
  broken query is a clean 500 rather than a truncated success envelope the user keeps as their "copy of my data".
- Stream row by row: no unbounded `fetchAll`, no silent row cap. Where the driver buffers whole results by default,
  suspend that for the streamed reads and restore the previous state in `finally`.
- **Included:** account profile, derived/learning/usage data, counters, support tickets and messages, notifications,
  sign-in device list, subscription and billing metadata, activity log, and the non-secret metadata of any machine
  credentials the subject owns.
- **Excluded, always:** password hashes, MFA secrets and recovery codes, remember-me token values, API bearer/validator
  hashes, other users' identities (a referral exports "made"/"joined", never the counterpart's id or email), and internal
  admin/security provenance.
- The document opens with a prose note saying what it covers and where to send a broader access request. Never restore a
  literal "everything we hold" promise to a bounded self-service channel.
- Log the export as an activity event **after** a complete document was produced. Rate-limit it per account — it is
  expensive, password-gated, and rarely legitimate more than a few times a day.

### 2.3 `privacy.deletion`

```
request ── password re-auth (under a row lock) ──► scheduled(+grace)
                                                     │
                          user cancels ◄─────────────┤
                                                     │  grace lapsed (DATABASE clock)
                                                     ▼
                   snapshot ► erase ► anonymise(strict) ► verify ► delete row ► receipt
                                                     │
                                       any postcondition fails ──► ROLLBACK, account intact
```

1. **Request** requires the password, verified under a lock on the account row. Scheduling also revokes anything granting
   continued access on the subject's behalf (API credentials; sessions, if your model calls for it).
2. **Grace** is a stored due date, not a timer. The user can cancel from the same surface, and both the profile and the
   global chrome show a standing notice while it is pending.
3. **Past-due is decided by the database**, in one comparison the database evaluates
   (`due IS NOT NULL AND due <= CURRENT_TIMESTAMP`), never by reading a naive datetime back into the application's
   timezone. Re-read it under the lock: the row may have been extended or already erased since the outer check.
4. **Snapshot** the ids of rows that must *survive pseudonymised*, before the first destructive statement. Verifying "the
   identifier is gone" against captured ids is the only check that cannot be satisfied by the rows having simply vanished.
5. **Erase** the subject's own data from the explicit inventory. Null out columns that *point at* the subject from
   somebody else's row (a surviving account's referrer, a ticket's assigned staff member).
6. **Anonymise strictly.** Support-thread anonymisers and legal-hold pseudonymisers routinely swallow exceptions per
   statement so they cannot break unrelated flows. In the deletion path they must run in a mode that **throws**. This is
   the prerequisite, not a side effect.
7. **Verify every postcondition**, naming the offending table: nothing left in any erase table; every snapshotted retained
   row still present, with no direct identifier and with the legal-hold pseudonym stamped.
8. **Delete the account row**, asserting exactly one row was removed.
9. **Files after commit only.** Attachment/media unlinks go through a durable purge queue drained after the transaction
   commits; a failed unlink stays queued. Unlinking first leaves rows pointing at deleted files when the transaction rolls back.
10. **Receipt** — a fixed-shape record of what was erased, what was retained, the pseudonym subject and the timestamp,
    logged as an admin/activity event.

**One code path.** Self-service deletion and the lapsed-grace purge are the *same* function called from two places, never
two implementations of the sequence. A duplicated deletion path gets its next fix applied to one copy.

**What survives, and why.** Pseudonymised proof-of-use and billing rows (Art 17(3)(e): defence of legal claims —
chargebacks), anonymised support-thread *text* while the files are deleted immediately, and whatever financial records
tax law requires. Everything the policy calls "profile, learning data, chat history and behavioural logs" goes.

**Legal hold.** Retained rows carry a stable one-way subject pseudonym so a dispute can still correlate a billing record
with a proof-of-use record. Derive it from a **dedicated secret** — not the MFA key, not a constant — and derive it
**first**, before any destructive statement, so an unconfigured deployment aborts cleanly. Pre-flight the key's presence
before the first file unlink.

### 2.4 `privacy.retention`

**A committed matrix doc** (`.docs/reference/data-retention-matrix.md` or the project's equivalent), one row per data
class: storage, current lifecycle, the setting/job enforcing it, the policy decision. It is a recommendation until the
owner accepts it, and **acceptance is not arming**. A matrix naming a window that no code enforces is a promise the
product is not keeping — every row states which job enforces it, or says plainly that none does yet.

**A runner.** CLI-only, denied by every server layer, with its own SAPI guard.

- Bare invocation is a **counts-only dry run**. `--apply` additionally requires an apply flag (say
  `RETENTION_APPLY_ENABLED`) held in the per-environment secrets file, read from the process environment or the loaded
  `.env` — never in `.env.example`, never written by deploy — so shipping the file, or scheduling the wrong command,
  cannot delete anything. The runbook says which machine-local file sets it.
- Each destructive loop selects at most a few hundred ordered primary keys, deletes exactly those, and can resume. The
  invocation is capped by rows and seconds and returns `truncated` so the next run continues.
- One advisory lock prevents concurrent runs. **Namespace the lock by schema** — lock names are server-scoped, and a
  staging deploy once waited fifteen minutes on production's worker for exactly this reason, because both used the same
  literal name on one server.
- Cutoffs are computed in the caller and **bound as parameters**, never inlined as `NOW() - INTERVAL`. That is what makes
  a 24-month period testable by advancing a clock instead of waiting two years. It is the second sanctioned ONE CLOCK
  exception (SKILL.md §6.1): a PHP-computed cutoff compared with database-written timestamps tolerates hours of skew at a
  scale of days — it does not *remove* the timezone mismatch, it makes it harmless.
- The status record keeps **one latest fixed-shape summary: job names, windows, counts.** Never row ids, payloads,
  emails, URLs or error text — error detail goes to the server log. A stale `running` record displays as `interrupted`.
- Every step is independently guarded and the run returns a report; **success is judged on the report's empty `errors`
  map, not on the absence of an exception.** A runner that swallows per-step failures will otherwise always look healthy.
- Deterministic, not opportunistic. A dice roll on an idle surface deletes nothing for a fortnight, and the policy says
  "automatically deleted".

**A scan that proves it.** A read-only, bounded, introspective sweep answering what the deletion path cannot answer about
itself: does any row anywhere still name a user id that no longer exists; are there orphaned files on disk; are there
accounts whose scheduled deletion lapsed and never ran; are there retained records still holding an un-minimised
third-party payload. Report **coverage** separately from findings — a clean scan that silently skipped half the schema is
not a clean scan.

**Minimise at ingestion.** Any third-party payload you retain (webhook bodies especially) is reduced by an **allowlist**
before it is written, so a provider that starts sending a new field does not silently fill a two-year archive with it. A
denylist inverts the failure. Provider bodies routinely carry the person's name, email, card brand/last four and *signed
portal URLs* — the last being a live capability that a "pseudonymised" row and a GDPR export would both hand back.

### 2.5 `legal.pages`

**The set:** Terms of Service, Privacy Policy, Refund Policy, Licences & Credits (third-party data, fonts, media,
libraries), a Cookie Policy if the privacy page does not cover it, and a Subprocessors page once you have processors
worth listing. Pricing is [billing.md](billing.md)'s.

- **Server-rendered, working with JavaScript disabled.** Payment-provider domain review and non-JS crawlers read these
  pages; a client-rendered legal page is an empty page to both.
- The copy lives in **exactly one place**. If the project has an SPA and a server renderer, only one of them owns the text.
- Each page carries a visible "Last updated" date.
- Public legal views are self-contained partials: no `session_start()`, no `header()`, no page boilerplate — output has
  already begun by the time they are included.
- They must be routed in **both** the dev and production routing layers (`.htaccess` and the dev router, or the
  equivalent pair) or they 404 in exactly one environment.
- **Licence attribution is derived from what was actually rendered**, not from a static source→licence table. A
  per-surface credit driven by the rendered rows' own provenance column is correct in both directions; a lookup table is
  wrong in both.

### 2.6 `legal.reconciliation`

**The rule:** any change to what is logged, retained, exported, or which third party processes data updates the policy
**in the same phase**. Not the next one.

**Why "same phase".** The failure this prevents is a published policy that describes last quarter's architecture: it
names one payment provider while the code charges through another, or promises a retention window no job enforces, or
omits a processor that has been receiving data for months. Nobody notices from outside, the gap widens silently, and it
is discovered by the person least able to forgive it — a user exercising a right the policy promised, or a regulator.
Deferring the policy edit to "a documentation phase" is how every one of those starts.

**The method:** a reconciliation document holding implemented facts the current policy does not describe accurately,
grouped by role/data class; a table of parties — processor, independent controller, customer-selected recipient — with
the wording each needs and what still must be confirmed; dated evidence with primary-source links, including negative
results; a section-by-section redline brief for the public copy; and a checklist of remaining external approvals
(counsel, accountant, hosting facts). The copy is edited **once, from that document**, after the checklist closes.
Distinguish *controller* from *processor* per data class — a product storing customer-supplied end-user data is a
processor for that and a controller for its own account data, and one policy has to say both.

## 3. Invariants

Each rule, then the reasoning that produced it.

1. **The export inventory and the deletion inventory are one declared list, and drift is prevented by a mechanism, not by
   discipline: a runtime assertion sorts both key sets, compares them, and throws.** Two hand-maintained lists always
   drift. Every registry of per-user records — tables, and notification kinds too — is a closed list some constant or
   assertion enforces, so a new one cannot be added without deciding its export and erasure treatment. The assertion
   turns "someone forgot" into a failing request during development instead of a subject-access complaint.

2. **The delete list is explicit; only the scan introspects.** In one codebase five tables — an activity counter, two
   progress tables, a usage meter and referrals — had no cascading foreign key and were in neither purge path, so they
   survived every "permanent" deletion for years. The fix was to add them to the explicit list *and* add an introspective
   scan that names the next one. A `DELETE` generated from a schema scan would eventually erase an admin-action log
   because its column happens to be called `user_id`.

3. **Anonymisation is a prerequisite of deletion, verified against a pre-erasure snapshot, inside a transaction the caller
   owns, and a failed verification rolls the whole thing back.** Anonymisers written for support threads and legal holds
   routinely swallow every exception per statement, so that one bad row cannot break an unrelated screen. Called from a
   deletion path in that mode, a failed "strip the direct identifier" leaves the account row deleted, the support ticket
   still carrying its `user_id`, and the user told "deleted permanently". Without a transaction there is nothing for a
   failed verification to undo. A refused deletion is recoverable and honest; a half-completed one is neither.

4. **One clock, and it is the database's.** The grace deadline is written by the database and must be compared by the
   database — in one codebase the same mistake had been made at three separate sites. Reading a naive datetime back
   through the application's timezone skews by the offset in both damaging directions — the harmful one **purges a user
   still inside their 14-day grace window on a routine sign-in**. Use `CURRENT_TIMESTAMP` rather than a vendor-specific
   `NOW()` so the same predicate runs against fixtures.

5. **The legal-hold pseudonym uses its own secret, fails closed, and rotating it orphans every pseudonym already stamped.**
   One implementation's salt read an environment variable that was never populated, so it was unconditionally a literal
   string committed to the repository — a 16-hex pseudonym over a small integer id, reversible by enumerating a few
   thousand ids, while the policy told users those records were pseudonymised. Give it a dedicated key: an MFA key can
   never be rotated (it decrypts stored secrets), while a pseudonymisation salt *should* be rotatable after exposure.
   Existing pseudonyms cannot be re-derived, so count the stamped rows in each retained table before any rotation.

6. **Retained third-party payloads are minimised by an allowlist at ingestion.** One stored webhook body carried the
   subscriber's name, email, card brand and last four, and **signed customer-portal URLs** — a live capability, handed
   back inside the GDPR export and kept for two years on rows the policy called "pseudonymised". A denylist silently
   retains whatever field the provider adds next.

7. **Password re-authentication gates both export and deletion; the subject id comes from the session.** A hijacked
   session should not be able to exfiltrate a full PII dump or destroy an account, and an id taken from input is an IDOR
   waiting to happen.

8. **Preflight every export query before the first response byte.** Once `{"success":true` is on the wire you cannot take
   it back; a query that throws mid-stream produces a truncated document that looks complete to the person who
   downloaded it.

9. **A new user-referencing column refuses the export until it is classified.** Fail-closed beats silent omission: an
   unclassified column is data the user asked for and did not receive, and nobody notices that from outside.

10. **Never export credentials or the other party's identity.** Password hashes, MFA secrets, recovery codes,
    remember-me values and API validator hashes are security material, not personal data the subject needs. A referral
    exports both directions of the relationship without exposing the counterpart's numeric identity.

11. **Files are unlinked after commit, through a queue that survives a failed unlink.** Filesystem work is not
    transactional. Purge files only after the row delete commits, or a failure leaves an account whose attachments are
    gone: unlinking first leaves rows pointing at deleted files when the transaction rolls back, and doing it without a
    queue loses the file on a transient error.

12. **Retention runs dry by default; apply needs a machine-local flag that deploy does not set.** Deploying the runner, or
    scheduling the wrong command, must not start deleting customer data. Removing the flag is the kill switch.

13. **Bounded batches, one advisory lock — namespaced by schema — and a `truncated` flag.** An unbounded delete on a live
    database is an outage; a restartable run with a resume marker turns a backlog into a series of quiet ticks. Advisory
    lock names are **server-scoped**, so a bare literal is shared by every schema on the box: read the lock name before
    you copy a runner, not after staging has blocked production for a quarter of an hour.

14. **The retention status record holds counts only.** A job whose purpose is deleting personal data must not accumulate a
    second copy of it in its own telemetry — no row ids, addresses, URLs or error text.

15. **A retention runner that returns a report instead of throwing must be judged on the report.** Each step is guarded so
    one failure does not stop the rest, which means "no exception" is not "success". The caller's health record reads the
    `errors` map; step *names* are safe to surface, raw exception text is not.

16. **Cookieless analytics is the default, so the banner can be honest.** Aggregate `(day, path, referrer_host)` counters
    with no identifier, no IP and no cookie are not personal data, have nothing for an erasure request to reach, and
    remove a whole section of consent complexity. The beacon is unauthenticated, so rate-limit it and normalise the path
    to a known set.

17. **The consent banner must work with JavaScript off and must ship visible.** A real `<form method="post">` +
    set-cookie + 303 redirect is the no-JS path; revealing the banner with JS made its late paint the mobile LCP, and a
    service-worker-cached shell from an older release once made it vanish for every returning visitor. Re-assert
    visibility in both directions on boot.

18. **Legal pages are server-rendered and their copy exists once.** Merchant-of-record domain checks and non-JS crawlers
    read them, and two renderers owning the same clause is how a price or a retention promise silently forks.

19. **Policy and code are reconciled in the same phase as the change.** Every logging, retention, export or provider
    change re-reads the policy sections it touches. A policy left one phase behind is a published statement to users that
    is no longer true, and nothing outside the codebase will report it — which is why this is a phase-completion check
    and not a periodic review.

20. **Accepting a retention baseline is not authority to delete.** Owner acceptance, counsel sign-off on the public
    wording, a supervised dry run, and arming the flag are four separate steps, in that order.

21. **Never claim a stronger promise than the mechanism delivers.** A scrub that cannot rewrite structural attributes
    **counts and reports** what survived instead of saying "removed permanently"; a backup bucket gets a residency
    sentence only after the endpoint, a landed backup and the old bucket's deletion were each verified; a visual
    redaction overlay is a CSS cover — the underlying data still holds the text, and the UI has to say so.

## 4. Reference implementations

*Pointers into the author's own repositories live in the optional `local/pointers/<name>.md` overlay,
which is not shared. The contract in §2 and the invariants in §3 stand on their own: they say what to
build and why, not where one team's copy happens to sit.*

## 5. Decision points

| Decision | Default | Notes |
|---|---|---|
| Deletion grace period | **14 days**, user-cancellable | A B2B tool whose operator *is* the customer can defensibly delete immediately; a consumer product wants the grace window. |
| Where the grace is enforced | At **login** and on **every authenticated request** | Cheap (the row is already being read), and it removes the need for a cron to be reliable. Add an admin action for the immediate case. |
| Analytics model | **Cookieless aggregate counters** | Anything with a per-visitor identifier moves you into consent-gated territory and into the export/deletion inventories. |
| Consent storage for signed-in users | **Cookie + server row** | The server row survives a device change and is what an export can show. Commonly missing — see §6. |
| Export format | **JSON**, streamed, one document | CSV per table is more portable for a spreadsheet user and much more work; revisit only if asked. |
| Behavioural / security log retention | **12 months** | Disclosed in the policy, from the same constant the retention job reads. |
| Billing / proof-of-use retention | **24 months** | Chargeback-defence window. Derive the constant from one definition shared by the policy text, the log tiers and the retention job. |
| Retention of a *live* subscriber's billing rows | **Leave them** | Deleting a current customer's billing history is not a call a sweep should make silently; the tax/accounting carve-out is real. Prune only rows with no owning account. |
| Statutory accounting period | **Unpromised until an accountant confirms it** | Leave it blank rather than inventing a number. |
| Who publishes the subprocessor list | **A maintained page**, not inline policy text | Vendor facts move; a linked page changes without a policy revision. |
| Arming the retention runner | **Owner → counsel → supervised dry run → arm** | Then schedule daily apply. Removing the env flag is the kill switch. |

## 6. Gaps and design briefs

Each is a **design brief only — no worked example ships with this file.** Record a pointer in the
optional `local/pointers/` overlay if you build one.

**G1 — Consent versioning and a server-side consent record.** The common state is a consent cookie storing the choice and
nothing else: no policy version, and no server row for signed-in users. Build: a `PRIVACY_POLICY_VERSION` constant beside
the app version; a consent cookie carrying `choice|version|timestamp`; for a signed-in user a `user_consents` row
(`user_id`, `category`, `choice`, `policy_version`, `decided_at`, `source`) written on the same action; the banner
re-shows when the stored version is older; the export includes the consent history and deletion erases it. Keep the
cookie authoritative for anonymous visitors so the no-JS path is unchanged.

**G2 — Rate-limiting the export.** An export action commonly ships unthrottled, because a method/CSRF/body-size request
guard looks like protection and is not a limiter. Build a per-account bucket (a small number of exports per 24h) on the
project's existing limiter, refusing with the retry time. Password re-auth already blunts abuse; the limit is about cost
and about a compromised session grinding through repeated dumps.

**G3 — A user-facing deletion receipt.** An internal receipt is the usual state, and the subject is sent nothing. Build:
on scheduling, an email confirming the date and how to cancel; on completion, a final email to the address on file (sent
*before* the address is erased, or from a value captured in the same transaction) stating what was removed and what is
retained under legal hold, with the pseudonym subject so a later dispute can be correlated. Route it through
`notifications.md`'s emitter — best-effort, never rolling back the deletion.

**G4 — A published subprocessors page.** The structure is the settled part: separate tables for processors, independent
controllers and customer-selected recipients, with captured-content hosts disclosed separately. Publishing it is the half
that gets deferred. Build a `/subprocessors` route in the legal set, copy in the same single-source file, each row naming
the party, purpose, role and processing region, with a "last reviewed" date.

**G5 — A separate cookie policy page.** Folding cookies into a privacy-policy section is the usual choice. If the banner
ever offers per-category choices, a dedicated page listing each cookie by name, purpose, category and lifetime becomes
the honest surface. Low priority while the answer is "session + CSRF + consent + optional remember-me".

**G6 — Token garbage collection.** This is the row a retention matrix names and no code enforces: expired or revoked
verification, reset, remember-me and pairing tokens have per-class cleanup at best. Build one job in the retention runner
expiring every token class no later than 30 days after expiry/revocation, with the same batching and reporting as the
other jobs. Coordinate with `identity.md`, which owns the token tables themselves.

## 7. Manifest rows

| Capability id | Tier | Done means |
|---|---|---|
| `privacy.consent` | 1 | A banner that works with JS disabled, ships visible, stores the choice in a first-party cookie with the policy version, and is honest about what is actually set — with cookieless analytics as the default that makes it honest. |
| `privacy.export` | 1 | One declared inventory shared with deletion, a throwing parity assertion, every user-referencing column classified or explicitly excluded, password-re-authenticated, preflighted, streamed, containing no credentials or third-party identities. |
| `privacy.deletion` | 1 | Request → re-auth → cancellable grace → database-clock due date → snapshot/erase/strict-anonymise/verify/delete in one transaction that rolls back on any failed postcondition, files purged post-commit, receipt recorded, legal hold pseudonymised under a dedicated fail-closed secret. |
| `privacy.retention` | 1 | A committed retention matrix, a CLI runner dry by default and armed only by a machine-local flag, bounded restartable batches under a schema-namespaced advisory lock, a counts-only status record, and an orphan/PII scan that reports its own coverage. |
| `legal.pages` | 1 | Terms, Privacy, Refund and Licences server-rendered from single-source copy, routed in every routing layer, working with JavaScript disabled, each carrying a last-updated date. |
| `legal.reconciliation` | 1 | A reconciliation document exists, and the project's phase checklist requires any logging/retention/export/provider change to update the affected policy sections in the same phase. |
