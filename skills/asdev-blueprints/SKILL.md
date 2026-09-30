---
name: asdev-blueprints
description: The capability inventory a web project should have — tiered contracts, invariants and definitions of done for environments, auth, admin and RBAC, GDPR, legal pages, notifications, support, a machine API, billing, search and gamification. Use ONLY to decide whether a capability exists and meets the standard: scaffolding a new project, auditing what a project is missing or whether it is launch-, production- or GDPR-ready, or adding a capability it lacks. Not for work on existing code, styling, debugging, running scanners or test suites, or a project's own domain features.
---

# Platform Blueprint

*Plain markdown — any AI coding agent can read it; nothing depends on a particular harness.*

Three sibling projects each re-derived the same platform independently — three TOTP implementations,
three migrators, three mailers — and each learned invariants the others never heard about. This skill
is the layer they converged on, written down once: **what must exist, by when, and with which
guarantees.** It does not hold code. Each capability is a *contract* (architecture-agnostic data,
surfaces, behaviour) plus *invariants* (the rule and the incident that produced it), and — where the
optional `local/` overlay is installed — a *pointer* into one team's own repositories.

**What this skill owns vs. what it links to.** Code idiom and per-project cheat sheets are the
`asdev-conventions` skill — run its context router before writing code. Deterministic checks are the
`asdev-web-audit` skill. Planning gates, the `.docs/` workflow, git/deploy topology and orchestration are the
global instructions. Domain logic is each project's `AGENTS.md`. This skill never restates those;
when they conflict with a reference file here, the more specific project file wins and the reference
file needs a fix (§6).

## 1. Which mode you are in

Decide once, say which, then follow that procedure.

| You are… | Mode | Output |
|---|---|---|
| starting a project that does not exist yet | **Scaffold** (§2) | Tier 0 in place + first manifest |
| asked what a project lacks / whether it is ready / to compare it to the standard | **Audit** (§3) | a refreshed manifest + a gap report; no building |
| about to build or change any capability in the inventory (§5) | **Build** (§4) | the capability, its tests, one manifest row updated |

A request can chain modes (audit → build the top gap) but each mode finishes and reports before the
next starts; the owner decides what gets built. Proportionality applies throughout: an audit is a
read, not a build; a Tier-3 capability the project has marked `n/a` is not "missing".

## 2. Scaffold

1. **Ask what is not derivable, once, as one question:** project name and domain, what it is (one
   paragraph), and the Tier-3 profile — billing, referrals, gamification, teams, SSO, email
   administration, PWA — and, inside the machine API, whether machine-generated content is part of
   the product (`mapi.work`, `mapi.test-accounts` and the write half of `mapi.openapi-clients` apply
   only then; the read + schema half is assumed). Everything else in Tiers 0–2 is assumed yes; a
   project that genuinely lacks a Tier 1–2 capability records `n/a` with a reason rather than
   skipping it.
2. **Pick the idiom** from `asdev-conventions/references/projects.md`. Default for a new SaaS:
   a REST front-controller with PDO — the newer, stricter of the idioms there. Never mix idioms.
3. **Lay down the files** from `assets/`: `env.example.template` → `.env.example` (then `.env`, never
   committed); `AGENTS.template.md` → `AGENTS.md` and `CLAUDE.template.md` → `CLAUDE.md` (pointer
   only); `docs-skeleton/*` → `.docs/`; `platform-manifest.template.md` →
   `.docs/reference/platform-manifest.md`; `htaccess-deny.snippet` → the project's `.htaccess`, with
   the directory list adapted; `auditignore.template` → `.auditignore`; `audit-baseline.template.json`
   → `.audit-baseline.json`; `pre-commit.template.sh` → `.git/hooks/pre-commit` (executable; it
   delegates to the one canonical `asdev-web-audit` copy — verify with `harness_parity.py`);
   `ci-workflow.template.yml` → `.github/workflows/ci.yml`, replacing every `<PLACEHOLDER>`. Add
   `.gitignore` (`.env`, `.claude/`, `.aiexclude`, `.tmp/`, runtime dirs).
4. **Build Tier 0** by reading [references/foundation.md](references/foundation.md) and implementing
   each `env.*`, `docs.*`, `http.*`, `release.*`, `db.*`, `test.*`, `ops.*`, `mail.*` row in the chosen
   idiom. The secrets test and the health endpoint are not optional; the staging lock and the
   server-level deny are **owner actions** — write them into the manifest's "Owner actions pending".
5. **Git:** `main` (production) and `staging` (the single shared development branch); first commit on
   `staging`. Deploy keys, webhooks and vhosts are owner actions.
6. **Write the manifest:** Tier 0 `done` (or `partial` with what is left), Tiers 1–2 `todo`, Tier 3
   per the profile. Fill the Tier-3 profile line and the idiom line.
7. **Stop.** Report the manifest and the owner actions. Tier ≥ 1 is built on request, capability by
   capability, in Build mode — not as part of the scaffold.

## 3. Audit

1. Read the project's `AGENTS.md`, its `.docs/reference/` index, and the existing manifest if any.
2. For every id in §5, open the matching reference file's **§7 "definition of done"** and check the
   project against it — by reading the code the pointer names, not by trusting a doc. `grep -l` for
   the mechanism (a table, a route, a runner, a test) is the cheap first check; read when it hits.
3. Classify each row: `done` · `partial` (say what is missing) · `todo` · `deferred` (why, and what
   changes the decision) · `n/a` (why). Note the reference the project would port from.
4. Rewrite `.docs/reference/platform-manifest.md` in full (it is generated, not hand-curated) and
   append an "Audit history" line. Create it if absent — an existing project gets the same file.
5. Write the report **into the project**, as `.docs/reference/platform-audit-<YYYY-MM-DD>.md`, and
   link it from the manifest's Audit-history row: per tier, what blocks the next tier, the
   highest-value gaps with their pointers, and every invariant from §6 the code contradicts — each a
   defect with file:line. The report is the evidence behind the manifest and lives beside it, never
   in a skill workspace or only in chat: a later session, another harness or another machine must
   find it by convention. When a new audit lands, move the previous report to
   `.docs/reference/archive/<YYYY-MM>/` per the global `.docs/` rotation rule. Do not build.

## 4. Build

1. Name the capability id(s). Read the matching reference file — §2 contract, §3 invariants, §4
   pointer, §5 decisions. Where the optional `local/` overlay is installed, `local/reference-map.md`
   and `local/pointers/<name>.md` add the author's own port-from paths and preserve lists; without it,
   build from the contract and the invariants. Read the project's `AGENTS.md` and run the
   `asdev-conventions` router for idiom.
2. Open the reference implementation and port it **in the project's idiom, preserving the named
   invariants** — not by copying files. The "what NOT to copy" list in §4 of each reference names the
   project-specific coupling to leave behind.
3. Every invariant that can be checked gets a test; the global falsification rule applies (each new
   guard shown RED once, for the right reason). Sensitive capabilities — auth, secrets, payments,
   deletion, machine credentials — follow the global rule on model tier and detached review.
4. If the change touches logging, retention, export or a provider: update the policy pages in the
   same phase (`legal.reconciliation`). If it adds a system a future session must understand before
   touching: add a `.docs/reference/<area>.md` and a line in `AGENTS.md`'s deep-reference map.
5. Update the manifest row (status, ported-from, decisions). **If the project has no
   `.docs/reference/platform-manifest.md` yet** — every existing project started before this skill —
   create it from `assets/platform-manifest.template.md` with the row you built filled in and a
   header line "partial: only the rows marked are attested; run the skill's Audit mode for the rest";
   every other row stays `todo`. A row you can attest in passing (you read the code) may be filled,
   but never guess — an unaudited `done` is worse than an honest `todo`. Add the manifest to
   `AGENTS.md`'s deep-reference map in the same change. A capability with no reference
   implementation (§5 marks them) is built from its design brief in §6 of the reference file and
   **becomes the reference**: when it ships, record its paths in the `local/` overlay and promote the
   brief to a pointer (see §7).

## 5. The inventory

Ids are stable; they appear in every manifest and in §7 of exactly one reference file. Read the
reference file before touching the capability.

**Tier 0 — before the first push to staging** → [references/foundation.md](references/foundation.md)

| id | one line |
|---|---|
| `env.secrets` | git-ignored `.env`, tracked placeholder-only `.env.example`, enforced by a test that runs first |
| `env.environments` | local / staging / production, per-environment secret resolution that fails closed, `APP_ENV`↔`DB_NAME` agreement |
| `env.staging-lock` | staging answers only on the tailnet, own database, own secrets, `noindex` on every response |
| `docs.layout` | `AGENTS.md` + `CLAUDE.md` pointer, `.docs/` working documents, `.docs/reference/` with the manifest |
| `http.deny` | dotfiles, markdown, CLI-only dirs and runners unreachable over HTTP; three layers |
| `http.headers` | security headers + CSP baseline, per-page relaxations explicit |
| `release.versioning` | one version constant, cache-busting from it, SW cache name in lockstep if a PWA |
| `db.migrations` | ordered, additive + idempotent, ledger, advisory lock, pre-dump, data-risk refusal, deploy hook; contended DDL rehearsed on the disposable database first |
| `db.backups` | scheduled + pre-migration dumps outside the docroot, bounded retention, off-site copy |
| `test.battery` | one runner as the release gate with its scope printed; database suites declared and run only against a disposable target (schema or pinned instance, process-env config); three-job CI (hosted or self-hosted on the VPS) with timeouts and path-based scope; `.auditignore` + baseline + delegating pre-commit hook; delta audit on a failing gate |
| `ops.health` | liveness endpoint with DB + clock + version, safe for an uptime monitor |
| `mail.transport` | one sender, validated `MAIL_FROM`, non-production never sends real mail |

**Tier 1 — before the first real user**

| id | one line | reference |
|---|---|---|
| `auth.core` | register / login / logout, hardened sessions, enumeration-resistant, lockout | [identity.md](references/identity.md) |
| `auth.verify-email` | verified-email gate, hashed single-use tokens on the database clock | identity.md |
| `auth.password-reset` | forgot / reset with the same token rules, sessions revoked on change | identity.md |
| `auth.password-policy` | length floor, breach check where available, no composition theatre | identity.md |
| `auth.remember-me` | split selector/validator token, rotation on use, revoke-all | identity.md |
| `auth.mfa` | TOTP + hashed recovery codes, secrets encrypted with a key that travels with the *database* (a cloned database needs its key), re-auth to change | identity.md |
| `auth.captcha` | per-surface Turnstile, server-verified, defined behaviour when the provider is down | identity.md |
| `auth.rate-limits` | per-IP and per-account, metered after the check, on every auth and guest surface | identity.md |
| `account.profile` | profile page + dashboard | identity.md |
| `account.management` | change email (re-verify new, notify old), change password (re-auth), MFA setup, sessions | identity.md |
| `account.settings` | timezone, customisation, consent control | identity.md |
| `admin.panel` | the admin shell; authority checked server-side first on every admin surface | [admin.md](references/admin.md) |
| `admin.rbac` | named permissions via `can()`, ranks, nobody acts at or above their own rank | admin.md |
| `admin.users` | list / search / suspend / role / manual entitlement grant with expiry | admin.md |
| `admin.settings` | whitelisted site settings with types and bounds; operator secrets admin-editable, encrypted under the `.env` master key, `.env` as fallback | admin.md |
| `admin.kill-switches` | maintenance mode + feature kill switches, read first, fail closed | admin.md |
| `admin.audit-log` | append-only actor / target / action, no payload secrets | admin.md |
| `admin.dashboard` | server-computed, cached stats | admin.md |
| `privacy.consent` | strictly-necessary vs consented, stored, re-asked on policy version; cookieless analytics default | [privacy-legal.md](references/privacy-legal.md) |
| `privacy.export` | inventory-driven self-service export, re-auth, rate-limited | privacy-legal.md |
| `privacy.deletion` | request → grace → anonymisation prerequisites that throw → delete → receipt; legal hold | privacy-legal.md |
| `privacy.retention` | committed retention matrix + runner with dry-run default and bounded batches | privacy-legal.md |
| `legal.pages` | terms, privacy, refund, licences, cookie policy — server-rendered, JS-off | privacy-legal.md |
| `legal.reconciliation` | policy and code change in the same phase | privacy-legal.md |
| `notify.user` | one persistence seam, best-effort emitters, inbox + badge + mark-read | [notifications.md](references/notifications.md) |
| `notify.admin` | same seam, admin audience | notifications.md |
| `notify.email` | optional email channel under consent and quotas | notifications.md |

**Tier 2 — before public launch**

| id | one line | reference |
|---|---|---|
| `mapi.credentials` | machine credentials hashed at rest, shown once, per environment, scoped, revocable | [machine-api.md](references/machine-api.md) |
| `mapi.gates` | kill switch read first, per-scope toggles, grants per credential, operator controls | machine-api.md |
| `mapi.read` | a committed, machine-readable table allowlist with open / limited / blocked tiers; credential, session and secret tables blocked; `users` at most an aggregate count; keyset paging | machine-api.md |
| `mapi.schema` | schema status endpoint: tables, columns, fingerprint, migration ledger; no secrets | machine-api.md |
| `mapi.work` | work orders: claim → lease → submit → canonical validation → commit; idempotent; draft-only | machine-api.md |
| `mapi.test-accounts` | staging-only temporary, address-bound, immutable accounts; five gates refuse production | machine-api.md |
| `mapi.ip-allowlist` | per-credential CIDR allowlists, both address families | machine-api.md |
| `mapi.openapi-clients` | OpenAPI as source of truth; thin CLI + MCP reference clients, dry-run default | machine-api.md |
| `support.public` | guest tickets: signed guest link, captcha, per-IP limits | [support.md](references/support.md) |
| `support.user` | logged-in portal with relaxed limits and history | support.md |
| `support.admin` | one queue: assign, status, reply, anonymised on account deletion | support.md |
| `support.attachments` | outside the docroot, opaque names, access-checked download, purge at every delete site | support.md |
| `seo.core` | sitemap, robots, canonical/OG/JSON-LD, SSR for public pages, `noindex` off production | foundation.md |
| `search.core` | FULLTEXT or per-entity index, ownership-scoped queries, public vs private indexes | [engagement.md](references/engagement.md) |

**Tier 3 — where applicable** (the manifest's profile line decides; `n/a` needs a reason). One
cross-tier dependency: `billing.*` requires `legal.pages` done first — merchant review and domain
verification read `/terms`, `/privacy`, `/refund` and `/pricing` without JavaScript.

| id | one line | reference |
|---|---|---|
| `billing.provider` | REST-via-cURL behind an interface, sandbox keys off production, Paddle default | [billing.md](references/billing.md) |
| `billing.plans` | plans as data, multi-duration, SSR pricing page | billing.md |
| `billing.webhooks` | signature → durable insert → ack → retryable domain step; idempotent by event id | billing.md |
| `billing.entitlements` | server-side resolution, manual grants, payer resolved per resource, non-prod mock only | billing.md |
| `billing.referrals` | reward on the friend's first paid invoice, clawback, self-referral refused | billing.md |
| `auth.sso` | Google / Apple sign-in — **design brief only** | identity.md §6 |
| `support.email` | support mailbox in Admin — live IMAP/SMTP view, stores nothing, no delete | support.md §6 |
| `game.xp-levels` | events ledger → derived XP and level, server-computed | engagement.md |
| `game.achievements` | idempotent awards keyed by (user, achievement), evaluated from the ledger | engagement.md |
| `game.streaks` | daily-activity calendar in the user's timezone, optional freezes | engagement.md |
| `teams.workspaces` | membership-only access (no implicit creator hold), owner/admin/editor/viewer with the rank rule, invites hashed and seat-capped, deleting a workspace hands projects back rather than cascading | local overlay |
| `integrations.webhooks` | leased deliveries with claims, host-exact (never substring) endpoint checks, a malformed delivery id repaired rather than fatal, enqueue non-fatal | local overlay |
| `pwa.service-worker` | network-first with no-cache fetches AND server `no-cache` on js/css (both layers), cache name in lockstep with the version; not having one is a legitimate recorded decision | local overlay |
| `admin.i18n` | one language file is the complete source of truth, others overlay it per key, every new admin string is a key rather than literal text | local overlay |

## 6. Invariants that cross domains

Each reference file carries its own, with the incident behind it. These hold everywhere and are the
first thing an audit checks the code against:

1. **One clock.** An expiry is written and read by the database's clock, never PHP's. Two deliberate exceptions: a day-granularity calendar comparison in the user's own timezone (streaks), where the *user's* day is the unit; and a coarse retention window (days) whose cutoff is computed in PHP and bound as a parameter so the runner is testable — skew of hours is harmless at that scale. Anything measured in minutes or hours (tokens, leases, lockouts, verification windows) gets no exception. *(identity, billing, machine-api; exceptions in engagement and privacy-legal)*
2. **Timestamps spell `NULL` / `NOT NULL`; booleans are read strictly** — never `!empty()`. *(foundation)*
3. **Migrations are additive and idempotent**; anything that can change existing data needs explicit owner approval and never rides the deploy hook. *(foundation)*
4. **Advisory-lock names are server-scoped** — namespace them by schema, or staging waits on production. *(foundation)*
5. **`.env.example` placeholders are enforced by a test that runs first**; secrets resolve per environment and fail closed. *(foundation)*
6. **Non-production is `noindex`, tailnet-only for staging, with its own database and secrets.** *(foundation)*
7. **Authority is checked server-side first** on every admin and machine surface; a kill switch is read before any *domain* refusal of the path it governs — transport guards (method, origin, CSRF, body size) legitimately stay ahead of it, so a hostile request never reaches a settings query. *(admin, machine-api)*
8. **Every token at rest is hashed, every secret is shown once**, and a credential can never mint a replacement. *(identity, machine-api)*
9. **Sensitive account changes re-authenticate** and notify the old address. *(identity)*
10. **Durable first, then ack**: a webhook is stored before it is acknowledged and the domain work is a retryable step. *(billing)*
11. **Export and deletion read one inventory; anonymisation is a prerequisite of deletion** and throws when it fails. *(privacy-legal)*
12. **Emitters are best-effort**: a notification never rolls back the write that caused it. *(notifications)*
13. **The machine API reads from a committed allowlist with explicit tiers, never a denylist**; credential, session and secret tables are blocked and `users` exposes at most an aggregate count; **machine content is draft-only** — it never goes live without human approval. *(machine-api)*
14. **Policy and code move in the same phase.** *(privacy-legal)*
15. **Everything a user uploads, and every per-user rendered document (attachments, exports, invoices, narration), is served through an access check**, from outside the docroot, with `nosniff`. Content-addressed shared media (generated audio, shared images) may live in the docroot for HTTP/SW caching — that is a design, not a defect. *(support, billing, machine-api)*
16. **Consuming a single-use thing — a reset token, a recovery code, a claim, an invite seat — is a conditional write judged on affected rows, under the row lock.** A read-then-update produced findings in three separate codebases independently. *(identity, machine-api, billing)*
17. **Anything enforced lives in a committed machine-readable artifact the code loads, never only in prose.** The read policy's prose copy drifted from its JSON (33 vs 34 blocked tables) while the JSON stayed right; the same rule is why the secrets policy is a test and the retention matrix has a runner. *(machine-api, foundation, privacy-legal)*
18. **The master key lives in `.env`; the individual secrets live encrypted in the database.** Operator configuration — mailbox credentials, provider keys, integration tokens — is admin-editable and diagnosable in the panel, stored under a per-purpose key derived from the master secret, with the `.env` value as a field-by-field fallback. "Secrets live in the `.env`" was a mis-statement; plaintext in the database is the defect. *(admin, foundation; owner decision 2026-08-23)*

## 7. Decisions already taken (defaults — the owner overrides per project)

- **SSO** is Tier 3 until the first project builds it; `identity.md` §6 is the brief.
- **Email administration** is a live mailbox view over a dependency-free IMAP/SMTP-over-TLS client:
  store nothing, no delete, no ticket conversion — decided after measuring that the mail host offered
  IMAP and authenticated SMTP but the PHP `imap` extension was unavailable and a package was not an
  option. Shipped twice on that shape; `support.md` §6 has the contract. Folder handling is the one
  open variant — fix a small set, or make the list configurable — but neither speaks `LIST`.
- **Idiom for a new project:** REST front controller + PDO — the newer, stricter idiom.
- **Service worker:** a decision, not a default — a PWA needs one; a project with no offline story is
  right to record that it deliberately has none.
- **The conformance checker** for a project is a future `asdev-web-audit` scanner (one scanner copy); this
  skill ships only its own `scripts/self_test.py`.

## 8. Maintaining this skill

- `python scripts/self_test.py` — every id in §5 is defined in exactly one reference §7 and present in
  the manifest template, the skeleton headings are intact, the assets are present, and the env
  template holds no populated credential. Where the optional `local/` overlay is installed it also
  verifies that every repository path the overlay cites still exists (`--projects-root` says where to
  look). It checks that pointers *exist*, not that they are right. Run it after editing any reference,
  and whenever a pointed-to file moves.
- **Editing the frontmatter description:** keep it under ~1,500 characters — the harness truncates
  the skills listing at roughly 1,535, and anything past the cut (measured 2026-08-23, when the
  exclusions fell off the end) is invisible to triggering. Re-measure after an edit that changes
  what the description **claims** — its scope, its trigger conditions, its exclusions or the
  capability list. A pure wording or tone change does not earn a 63-run probe. When it does, run
  `python scripts/trigger_probe.py local/evals/trigger-eval.json --skill asdev-blueprints --runs 3`
  (threads, sandboxed `claude -p`, only the Skill tool allowed — the runs can decide but not act).
  The probe is generic and takes any query file; the query set itself lives in the `local/` overlay,
  so point it at your own file if you do not have that overlay installed.
  Baseline to beat: **21/21** (measured 2026-08-27, 3 runs/query, fable-5) — every should-trigger
  query at 100%, and every should-not query either using no skill or correctly deferring to
  `asdev-conventions` / `asdev-web-audit`, which the probe reports per row. ⚠️ A score only means something
  if the runs reached the model: an expired CLI session turned every run into a 7-second auth error
  and the probe published **10/21**, which reads exactly like a description regression and invites a
  "fix" to something that was never broken. `trigger_probe.py` now detects an errored run and
  **aborts with exit 2** rather than scoring it — if it aborts, sign in again and re-run. Three
  measurement traps, all
  paid for: skill-creator's `run_loop.py` is useless on Windows (it waits on pipes with `select()`
  and scores every run not-triggered), and a detector that asks "was *a* skill used and does this
  skill's name appear in the output" is wrong in both halves — the name is in every run's
  available-skills list, and another skill's invocation reads as this one's. Compare the actual
  `input.skill` of the `Skill` tool call, as `trigger_probe.py` now does.
- **The skill is self-contained; project paths are examples, never dependencies.** Everything needed
  to scaffold, audit or build — every contract, invariant, procedure and template — lives in this
  directory and must be usable with no project open. The paths in §4 of each reference and in
  the `local/` overlay mean *"a working example of this lives here"*; a missing one costs a reader an
  example, never the contract. So: never cite an untracked or temporary document, an external URL or
  a GitHub repository. When a project's own doc holds knowledge the skill needs, **distil it into the
  relevant reference and ship any file as an asset** rather than linking it — a CI runbook cited this
  way in 2026-08 had vanished three days later, which is the failure mode. If you catch yourself
  writing "see <project> for how to do X", X belongs in a reference or an asset.
- **Adding a capability:** give it an id (`area.name`), a tier, one line in §5, a row in
  `assets/platform-manifest.template.md`, and a §7 row plus contract in exactly one reference file.
- **Promoting a brief to a pointer:** when a project ships a §6 capability, add its paths to
  `local/reference-map.md`, rewrite that capability's overlay pointer with the preserve list, and drop the
  "no reference implementation" marker here and in the manifest template.
- **A project contradicts a reference file:** the code is the evidence. Fix the reference (or record
  the project's deviation as a §5 decision) in the same session — a stale pointer is worse than none.
