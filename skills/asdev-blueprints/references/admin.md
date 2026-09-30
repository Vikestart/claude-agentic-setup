# Administration — platform contract

*Part of the `asdev-blueprints` skill. Tier 1. Read this before scaffolding, auditing, or building any of: admin.panel, admin.rbac, admin.users, admin.settings, admin.kill-switches, admin.audit-log, admin.dashboard.*

Related files: `identity.md` owns authentication, MFA and the account lifecycle a user drives themselves — this file owns *authority over other people's accounts and over the running site*. `privacy-legal.md` owns the erasure contract that admin deletion calls into. `notifications.md` owns the emitter seam, of which admin notifications are one audience. `foundation.md` owns `.env`, secret resolution and the environments. Visual rules for admin surfaces — settings cards, the three permitted dropdown styles, the design-restraint directive — belong in the project's own UI-contracts reference; read that before adding or restyling a control, and do not restate it here. Code idiom belongs to `asdev-conventions`.

## 1. Scope and timing

Tier 1 — before the first real user. The moment a stranger can create an account, someone has to be able to see it, suspend it, grant it something, and find out afterwards who did what. An admin panel retrofitted after launch is built under pressure, and the two things that get skipped under pressure are the audit log and the "you cannot do this to yourself" guards.

The kill switches are the part that is easiest to defer and hardest to add later: they have to be read *first*, on every request, and a switch bolted on after the fact ends up read in the middle of a handler where half the refusals have already run (§3, invariant 9).

Out of scope: what the admin panel *manages* (content, courses, generators, demos). That is domain, and belongs in each project's own `AGENTS.md`.

## 2. The contract

Architecture-agnostic. "Admin surface" means any operation that acts on data the caller does not own, or on the running site.

### Data (in concept)

- **Role** — a named role with a **rank** (an integer ordering) and a set of named **permissions**. Even a two-role project benefits from naming the permission rather than the role: `can('manage_users')` survives a third role appearing; `role_id == 1` does not.
- **Permission catalogue** — a code-level constant listing every permission key with a human label, grouped for the role editor. It is the source of truth; the database only records grants.
- **Setting** — a whitelisted key/value pair with a declared type, bounds, a coded default, and a chosen fail direction (see invariant 11). Never a secret.
- **Audit event** — append-only: actor, subject/target, action from a closed set, timestamp, source address, and a small structured `meta` of counts and labels. Never payload, never a credential.
- **Kill switch / maintenance flag** — a setting whose only job is to stop something. Read before the work, not inside it.

### Surfaces

| Surface | Operation | Authority |
|---|---|---|
| Panel entry | render the admin shell | the base "may use the panel" permission |
| Per-section route | open a section | that section's permission |
| Users | list/search, view details | user-read permission |
| Users | suspend/lock, change role, delete, provision, reset password | user-manage permission **+ rank rule** |
| Entitlements | grant/re-date/revoke a manual entitlement | user-manage permission |
| Settings | read all, write whitelisted keys | settings permission |
| Kill switches | flip maintenance / a feature switch | settings permission |
| Audit log | read, filter by action | a **higher** bar than performing the actions |
| Dashboard | aggregate figures | panel permission |

### Behaviour rules

- **Authority is checked server-side, first, on every admin operation** — including read-only ones. Admin chrome in the client is decoration.
- **The route table is a whitelist.** A section not in the table does not exist; an unknown segment falls back to the default section rather than reaching the filesystem.
- **A rank rule governs every mutation on another account**: nobody acts on a target at or above their own rank, and nobody acts on themselves through the admin surface.
- **Every state change that removes access carries its revocation in the same transaction** (see `identity.md` invariant 3): suspend/lock bumps the account's revocation counter and drops its persistent-login tokens.
- **Every mutation writes one audit row**, non-fatally, and the write failure is logged loudly.
- **Settings writes validate against the whitelist**, coerce to the declared type, clamp to declared bounds, and reject an unknown key rather than storing it.
- **Operator configuration — secrets included — is admin-editable**: the master key lives in the `.env`, the individual secrets live encrypted in the database. A mailbox password, a provider key, an integration token: stored AES-256-GCM under a key HMAC-derived from an existing master secret with a per-purpose label (never the master key itself), masked on read, with a Test-connection action beside the field; the `.env` value is the *fallback*, resolved field by field, so nothing needs a flag day. Secret setting keys end in `_password` AND are listed in the machine-API read policy's exact denylist — that table is published by prefix allowlist and the deny *pattern* matches `password` but not a bare `_pass`.
- **Kill switches are read before any *domain* refusal** in the path they govern — after the transport guards (method, origin, CSRF, body size), which exist so a hostile request never reaches a settings query. The shape is: request guard → session teardown → CSRF → `maintenance_mode` (503) → auth. A machine API reads its kill switch pre-auth, because it has no session to tear down.
- **The dashboard is aggregates only** — no customer content, no personal data beyond what identifying an account requires.
- **Admin notifications ride the same seam as user notifications**, with an admin audience rather than a second store — a signup worth flagging, a dead-lettered webhook, a failed background sweep. Contract in `notifications.md`; the only admin-specific rule is that the emitter resolves its recipients to *currently active* admins at delivery time, not to a list captured when the feature was built.
- **Every admin mutation carries the project's CSRF token**, and unsafe methods are refused without it. The mechanism (synchroniser token in a header, a hidden field, or a response header the client echoes) belongs to `foundation.md`'s request boundary; the admin-specific point is only that no admin action is exempt.

## 3. Invariants

1. **Every admin operation re-derives authority from the database as its first line, and the client's admin state is never a gate.** State it twice — as a standing security invariant ("every `/api/admin/*` method calls `requireAdmin()` as its first line; the SPA's admin gating is cosmetic") and in the admin controller's own docblock — and then *verify* it: count the gate calls against the public methods of every admin controller and expect the numbers to match. A single choke-point that every method already calls is also where you hang later policy (invariant 6) — there is nowhere to forget.

2. **The admin gate is one named function, not a re-typed role read.** The alternative arrives quietly: an inline `role_id` comparison at the top of one endpoint, a byte-for-byte copy at the top of the next, an `isAdmin()` helper, and a fourth variant in the machine-API path. They may be equivalent over HTTP *today* — if every admin entry point requires a common bootstrap that destroys a locked or past-due session before any of them runs — but four copies is four chances to drift, and the edge usually differs already: a *scheduled-but-not-lapsed* deletion refused by exactly one of them is the kind of difference nobody notices. The counter-example is what pays: because there is exactly one `requireAdmin()`, an "admins must hold a second factor" policy can be added in one place and be true everywhere (invariant 6). Write the gate once, and make every admin entry point call it.

3. **Gate on a named permission, never on a raw role integer.** `Auth::can('manage_pages')` is the shape. The reason is not tidiness: a role integer is a *fact about a person*, a permission is a *fact about an operation*, and only the second survives a new role. The cost of the other shape is concrete — a Moderator role that exists, is assignable, and grants nothing, because every gate asks `role_id == 1`, and it cannot grant anything without touching every gate.

4. **Rank orders roles, and nobody acts on a target at or above their own rank.** Enforce `target_rank <= my_rank` at list, open, edit and delete, and offer only roles at or below the actor's rank for assignment — which is what stops privilege escalation *through* user management. ⚠️ The same rule has to reach the role editor as well, or it is bypassable in one step — see invariant 27.

5. **Refusing to act on yourself is what keeps the last administrator alive.** Refuse self-targeting on role change, lock, deletion and scheduled deletion, and separately refuse to lock or delete *any* admin. Those two rules compose into a real guarantee: an admin cannot demote themselves, so there is always at least one. ⚠️ A panel with neither guard can be locked out entirely — an admin deletes a peer at equal rank, nothing counts the survivors, and eventually nobody can get in. The strictest line is also the simplest to reason about: a `mutableTarget()` that refuses self **and any admin**, with admin granted by SQL only and deliberately no API that can mint or demote one.

6. **A policy that must hold for every admin belongs at the single gate, not at each call site.** An optional "admins must hold a second factor" is enforced inside `requireAdmin()` — the one function every admin method already calls. It closes only the admin surface, never the rest of the app, so it can never lock someone out of the product itself; and it defaults **off** so the owner can enrol before switching it on.

7. **Suspension, locking and role removal end access now, not at session expiry.** Bump the account's revocation counter and delete its persistent-login tokens as part of the same write — on suspend, and inside the row-locked closure that toggles a lock. The finding behind it: before that, locking an account revoked only *future* logins while the open tab kept working. Unlocking deliberately bumps **nothing** — restoring access must not sign anyone out.

8. **Admin deletion goes through the one verified erasure path, and a failure says the account still exists.** The finding: an admin delete branch carried a hand-written table list that missed five tables with no foreign key to `users`, so a "permanent" deletion left behavioural and learning data behind — and it ignored the anonymisers' results, which swallow their own exceptions, so a failed pseudonymisation still reported success. Call the shared deletion function inside a transaction and, on any throw, roll back and answer "the account was NOT deleted and nothing was removed". Contract in `privacy-legal.md`.

9. **A kill switch is read before every *domain* refusal in the path it governs, and the order is the whole point.** Transport guards (method, origin, CSRF, body size) stay ahead of it — request guard → session teardown → CSRF → `maintenance_mode` → auth — and moving the settings read ahead of the guard would let a hostile request reach a query. What must never precede the switch is a *feature* refusal. The incident: with a public catalogue switched **off**, the default-category helper returned `''` and the allowlist predicate was false for *every* category — so a category refusal placed ahead of the switch turned every item URL into a 404 on an installation that simply has no public catalogue, where the correct answer was the ordinary app shell. Two further lessons ride along. ⚠️ It was invisible locally because the developer's switch was on and **staging ships dark** — a switch that is only ever tested in one position is not tested. And the regression guard asserts **order** (the switch read must appear before the refusal), because that is the actual property; the first attempt at falsifying it wrapped the code without reordering it and was correctly reported vacuous.

10. **Site settings are a whitelist with declared types and bounds; an unknown key is rejected, not stored.** A `DEFAULTS` map plus `BOOL_KEYS` and `INT_KEYS` (with per-key `[min, max]`) is the reference shape, and the setter throws on an unlisted key; a save action filtering against an explicit short list is the minimum. ⚠️ A store that accepts **any** key the client posts, sanitised only to `[a-z0-9_]`, is precisely how **setting-key drift** happens: an admin form saved `recaptcha_site_key`/`recaptcha_secret_key` while the public ticket flow read `recaptcha_site`/`recaptcha_secret`, so reCAPTCHA silently never engaged and nothing anywhere reported it. A whitelist turns that class of bug from a silent no-op into an immediate error.

11. **Choose the fail-open direction per key, not uniformly.** `signups_enabled` defaults **on** (a DB hiccup must not lock people out) while `upgrades_enabled` defaults **off** (a hiccup must not start selling upgrades that were never switched on). Safe means the opposite thing for those two keys, so a single global policy is wrong for one of them. And state the boundary: a setting is a *preference*, not a security control — anything that must hold when the database is unreachable belongs in code.

12. **Validate a setting whose value can break every client, at write time.** Refuse a forced-update floor that exceeds the deployed version, because a higher floor puts every client into a blocking update modal that updating cannot clear. A settings form is a remote code path into every browser; treat a bad value like a bad deploy.

13. **Secrets never live in the settings table in plaintext — and "secrets live in the `.env`" is not the rule either.** Operator configuration, secrets included, is admin-panel editable, because editing a `.env` needs file access on the server and must be repeated per environment, while a panel field is diagnosable with a Test-connection button. The shape is the one a TOTP seed store always had — master key in `.env`, the individual secret encrypted in the database under a per-purpose derived key, `.env` as a field-by-field fallback. ⚠️ Plaintext is the defect, not the location: an SMTP password read straight out of a `settings` table in the clear is the failure mode to grep for first. A crypto helper taking a caller-supplied key is the pattern, and it should use a **separate** key from the MFA one, so a leaked integration credential is not a step toward everyone's second factor.

14. **A value whose length can silently truncate is checked against the column, read from the column.** Read `information_schema` for the real width of a setting value, because MySQL in strict mode throws while a permissive mode truncates **silently** — and for something like a prompt template that means shipping half an instruction to every generation. Derive the limit; never hardcode it.

15. **The audit log is append-only, and its foreign keys do not cascade.** Make every reference `ON DELETE SET NULL`, and know why: a cascading `recording_id` would make a deletion event delete itself the moment it became the only record of what happened. The delete row passes no id for the thing it deleted at all, and carries the name in `meta`.

16. **The audit log is the worst place in the schema for sensitive data.** It is read by more people than the thing it audits and it deliberately outlives deletion. So `meta` takes counts and labels — a version number, a role, a name, a target id — and never a secret, never a token (the token *is* the credential), never a third party's email, never a before/after blob. Resolve actor and subject to emails by **JOIN at read time**, so a deleted account reads as "a removed account" rather than retaining the personal data of someone who asked to be forgotten. Attribution matters; it does not matter more than that.

17. **Audit writes are non-fatal but logged loudly.** An observability write must not fail the thing it observes — a successful suspension must not report failure because the audit table is missing during the post-deploy window where new code meets an old schema. But a *silently* incomplete audit log is worse than an obviously absent one: the entire value is in being able to trust that an absent entry means the action did not happen. Both reference shapes swallow-and-log; only one logs at a level you would actually notice, and that is the better half of the pattern.

18. **Reading the audit log is a higher bar than performing the actions it records.** Gate it on admin even where an editor may perform most of the recorded actions, because it is a cross-cutting view: it shows one person what happened in places they cannot otherwise open.

19. **Actions are a closed set of constants, not free strings.** Declare each action as a class constant plus an `ACTIONS` list used to validate read filters — a typo is then a fatal at write time, not a silently unfilterable row discovered six months later.

20. **The audit log needs a retention policy, and "later" is how it grows unbounded.** One reference has none and carries the absence as an open item; the other runs a **tiered** amortised prune on roughly one write in fifty, where proof-of-use and security events are kept longer than behavioural ones, and account deletion strips the identifier while keeping the rows a legal-hold defence needs (`privacy-legal.md` owns that reasoning). Decide the two retentions when you build the table, not when it is large.

21. **Admin figures exclude staff.** Exclude admin accounts from *every* dashboard number — including totals, and including the content they own and the traffic it receives — and report the admin count only so the UI can state what is being left out. The same holds for test accounts, with a subtler case worth knowing: machine-minted test accounts all carry a scheduled deletion date by design, which turned a "real people who asked to be deleted" figure into that number plus up to 53 throwaways. A dashboard figure that quietly counts your own staff or your own fixtures is not a metric, it is a lie with a number on it.

22. **Admin sees metadata, not content.** Say it in the admin controller's docblock: support does not need to read a customer's private content to do its job. If a support flow genuinely needs content access, that is a separate, audited, per-incident capability — not a property of being an admin.

23. **Impersonation ("log in as this user") is a capability to refuse by default.** Default to not building it. If a project genuinely needs it, the minimum is: a distinct permission, an audit row on entry *and* on exit, a session that is visibly marked as impersonated in every response, a hard time limit, a refusal to impersonate anyone at or above the actor's rank, and no ability to change credentials or delete while impersonating. Absent all of that it is an unlogged authority transfer, which is exactly what the audit log exists to prevent.

24. **Runtime DDL does not belong in a request handler.** An admin AJAX endpoint that runs `ALTER TABLE` on demand when a column is missing, or an `ensureSchema()` that creates and seeds the RBAC tables on first use, is convenient for a distributable CMS and it is genuinely self-healing — but it puts schema authority in a user-triggered path where a failure is a JSON error nobody reads, and it makes "which schema is this?" unanswerable. Schema belongs in the migrations runner (`foundation.md`); a handler that finds a column missing should **refuse with a clear message**, which is the posture to take everywhere (a `…SchemaReady()` predicate at the top of the handler, and a plain refusal when it is false).

25. **The highest-blast-radius admin actions re-authenticate, and the window that spares the repeated typing is fixed, server-side and never sliding.** A machine-API credential panel is the worked example, and the reasoning generalises: a step-up prompt per toggle turned one operator decision into dozens of prompts, and **a prompt an operator answers reflexively has stopped being a decision**. So one full verification opens a 15-minute window that drops only the typing — every action still names its blast radius, still locks the actor row, still re-checks the role, still carries CSRF, still writes its audit row inside the same transaction. Three properties make it safe rather than a bypass: the expiry is the verification moment plus the window and **using it never extends it**; the window is server-side session state with no cookie, no response field and no column, so a client can only be *told* it holds one; and a **named, asserted list** of always-fresh actions is exempt from it entirely — chosen by blast radius, not convenience. Whatever the equivalent set is in a new project (minting a credential, changing a role, deleting an account, rotating a key), name it in a constant and let a test assert the controller honours it.

26. **A destructive admin action states its target and its scope before it runs, and the confirmation is typed, not clicked.** Require the literal word `DELETE` for self-deletion; return a receipt naming what was actually erased. The rule generalises: an irreversible action on someone else's data should be impossible to trigger by muscle memory, and should answer with what it did rather than "done".

27. **⚠️ The rank rule must govern the ROLE editor, not only the user editor — otherwise it is decoration.** A project can apply `target_rank <= my_rank` rigorously everywhere a *user* is touched and still leave its `save_role` clamping a submitted rank only to `[1, 100]` and intersecting submitted permissions only against the full catalogue. Neither is capped at the acting user's own rank or own permission set, so anyone holding `manage_roles` can create — or edit their own — role at rank 100 with every permission, and walk straight past every user-side rank check. Where that shape exists it stays latent only while the seed happens to grant `manage_roles` to a single role, and a seeding default is not a control. Two rules close it: a role may never be given a rank above the actor's, and an actor may only grant permissions they themselves hold. Protecting the Administrator role specifically (fixed top rank, full permission set, undeletable via `is_system`) is the right idea applied to only one row.

## 4. Reference implementations

*Pointers into the author's own repositories live in the optional `local/pointers/<name>.md` overlay,
which is not shared. The contract in §2 and the invariants in §3 stand on their own: they say what to
build and why, not where one team's copy happens to sit.*

## 5. Decision points

| Decision | Options | Default |
|---|---|---|
| Role model | two fixed roles (`user`/`admin`) / ranked roles with a permission catalogue / roles present but every gate reads the role integer (the shape to avoid) | ranked roles + named permissions from day one; it costs one table and one class, and retrofitting gates is the expensive half |
| Who may create an admin | database only / in-app, rank-limited | in-app and rank-limited, **plus** an environment floor that refuses admin provisioning outside local/staging wherever a machine caller can reach it |
| Self-service admin actions | refuse all self-targeting | refuse self-targeting on role, lock, suspend and delete; allow it on reversible, low-risk grants |
| Acting on a peer admin | refuse entirely / allow at equal rank | refuse — an equal-rank peer war is a lockout waiting to happen, and demoting first is one extra click |
| Panel authority failure | 403 (API) / fall back to the default section (chrome) | 403 for any operation, fallback only for rendering a section |
| Settings store | whitelisted key/value table | key/value with a code-level whitelist, defaults, types and bounds |
| Secrets in settings | never / plaintext | never; if a distributable product forces it, encrypted under an environment key and masked on read |
| Maintenance mode | site-wide with an admin bypass / not implemented / robots-only | site-wide, admin-bypassed, read early, plus `Disallow: /` in robots while it is on |
| Audit storage | one dedicated append-only table / a general activity log plus aggregation | one dedicated table with a closed action set; aggregate *views* on top of it are free, an aggregated *log* is not |
| Audit retention | none / tiered amortised prune | tiered: security and proof-of-use rows longer, behavioural rows shorter, decided at build time |
| Dashboard freshness | live aggregates | live while the tables are small; cache to a settings row or a snapshot table before any figure needs a full scan (§6) |
| Admin login | one login for everyone, admin surfaces gated afterwards / a separate admin entry at its own path | one login — a second entry point is a second place to get lockout, throttling, MFA and revocation right, and where a separate one exists its reset flow is exactly where session revocation gets forgotten |
| Users list | unbounded / paginated with a sort-column whitelist | paginated with a clamped page size and a whitelisted sort column mapped to a real column name; every filter a bound parameter |
| Admin notifications | a `notifyAdmins()` seam / none | reuse the user notification seam with an admin audience — see `notifications.md` |

## 6. Gaps and design briefs

### admin.dashboard — server-side caching (design brief only; no worked example ships here)

Dashboards run their aggregates **live on every page view** until someone stops them. A young one is three or four queries with an index note and an explicit "the users aggregate scans `users`, which is small and bounded by signups; revisit if that ever stops being true"; a grown one fires roughly a dozen aggregates, several of them full scans joined back to `users`, on every load. Neither caches. Where that is the state, the contract this file states — "computed server-side with caching, never heavy queries per page view" — is **aspirational**, and the manifest must say so rather than claim it.

Build it as: one function that computes the whole snapshot, one durable store for the result (a settings row holding JSON, or a small `dashboard_snapshots` table), a TTL of a few minutes, a stamp of when it was computed rendered next to the figures, and a manual "refresh now". Compute it from the background worker if one exists, and fall back to computing inline when the snapshot is missing or stale so a fresh install still shows numbers. The stamp is not decoration: a cached figure with no age is indistinguishable from a wrong one.

### admin.rbac in a two-role project — how small it is allowed to be

A project with exactly two effective roles will express that as a role value read directly at the gate, and the cost only becomes visible when a third role appears: a Moderator that exists, is assignable, and grants nothing, because every gate asks `role_id == 1`. The minimum that avoids this is genuinely small and is worth building even for two roles: a constant mapping permission key to label; a table mapping role to permission keys, seeded so the existing role values keep their meaning; one `can(key)` reader loaded once per request; a `rank` integer on the role; and every gate calling `can()`. That is one class and one seed migration, and it is what makes the third role — a moderator, a support agent, a read-only auditor — a configuration change instead of a sweep through every endpoint.

### admin.users — active sessions and forced sign-out

An admin can lock an account (which revokes everything) but cannot see or revoke a *single* device. The rows already exist wherever remember-me does. See `identity.md` §6 for the user-facing half; the admin half is the same read plus a "sign out everywhere" that bumps the counter without changing the account's status.

### admin.audit-log — an integrity story

Every implementation here is append-only *by convention* — nothing prevents an `UPDATE` or `DELETE` by an operator with database access. That is a deliberate and reasonable stopping point for a small product. If a project ever needs more (a compliance obligation, a multi-operator team), the next step is a per-row hash chained to its predecessor and a verification job, not a promise in a docblock. Do not claim tamper-evidence you have not built.

### admin.kill-switches — a switch inventory

Switches end up scattered across the settings whitelist (`maintenance_mode`, `registration_open`, `email_verification_required`, a feature switch or two, plus the machine API's own) or sitting in a `DEFAULTS` map alongside ordinary preferences. Few codebases have a single place that answers "what can be switched off, what does each one stop, and who may flip it". Build that as a code-level constant — key, human label, what it refuses, required permission, and the default — and render the admin page from it. Then the switch that was added in a hurry cannot be the one nobody remembers exists, and the fail-closed direction is written down beside the switch instead of living in whichever handler reads it.

## 7. Manifest rows

| Capability id | Tier | Done means |
|---|---|---|
| `admin.panel` | 1 | A dedicated admin surface exists whose entry gate checks authority server-side before any work; sections are resolved through a whitelist with a per-section permission; an unauthorised caller gets 403 from every operation and never a partially-rendered section. |
| `admin.rbac` | 1 | Permissions are named keys in a code-level catalogue and every gate reads a permission, never a role integer; roles carry a rank; no actor may act on a target at or above their own rank or on themselves; the last administrator cannot be demoted or deleted. |
| `admin.users` | 1 | List/search, view details, suspend or lock with the revocation in the same transaction, change role, provision, reset a password, grant or revoke a manual entitlement with an expiry, and delete through the shared erasure path with an honest failure message. Every one writes an audit row. |
| `admin.settings` | 1 | A whitelisted key/value store with coded defaults, declared types, validated bounds and a per-key fail direction; unknown keys rejected; operator secrets admin-editable but stored encrypted under a key derived from the `.env` master key (never plaintext), masked on read, `_password`-named and denylisted in the read policy, with `.env` as the fallback; any value that could break every client validated at write time. |
| `admin.kill-switches` | 1 | Maintenance mode and every feature switch are read **before** any domain refusal in the path they govern (transport guards first), fail closed, are flippable only with the settings permission, and each has a stated effect on logins, writes and the machine API. Both positions of every switch have been exercised, not just the developer's. |
| `admin.audit-log` | 1 | An append-only table with a closed action set, actor and subject references that do not cascade on delete, a bounded `meta` of counts and labels and nothing sensitive, non-fatal-but-loud writes, a read gated at least as high as the actions it records, and a decided retention. |
| `admin.dashboard` | 1 | Aggregate figures computed server-side, excluding staff and fixture accounts, exposing metadata only. Cached with a visible computed-at stamp once any figure would otherwise scan a growing table. |
