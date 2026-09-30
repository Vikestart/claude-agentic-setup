# Foundation — platform contract
*Part of the `asdev-blueprints` skill. Tier 0, plus a Tier-2 SEO section at the end. Read this
before scaffolding, auditing, or building any of: env.secrets, env.environments, env.staging-lock,
docs.layout, http.deny, http.headers, release.versioning, db.migrations, db.backups, test.battery,
ops.health, mail.transport, seo.core.*

## Contents
1. Scope and timing
2. The contract
3. Invariants
4. Reference implementations
5. Decision points
6. Gaps and design briefs
7. Manifest rows

## 1. Scope and timing

Everything except `seo.core` is Tier 0: it must exist before the first push to `staging`, because
staging is a real deployment on real infrastructure from day one — reachable over the network (even
when locked down to a private address), backed by a real database, and updated by a real deploy hook.
A project without a secrets discipline, a deny layer, and a non-destructive migration path does not
get safer once it "goes live" later; it is already live the moment `staging` exists.

`seo.core` is Tier 2 (before public launch) and lives in this file rather than its own, because every
mechanism it needs — the canonical base URL, `IS_PRODUCTION`, the `X-Robots-Tag` header, the public
page map — is Tier-0 environment plumbing this file already owns. Splitting it out would either
duplicate that plumbing or force a forward reference into a file that hasn't been read yet.

This file does not restate `asdev-conventions` (how the code is written) or the global `CLAUDE.md`
(planning gates, the `.docs/` workflow, git/deploy topology, orchestration) — it owns only the
mechanisms and the tables/endpoints/flows a platform needs, architecture-agnostic to whether the
project is a REST front controller, an action-dispatch API, or a modular CMS.

## 2. The contract

**env.secrets.** Data: a git-ignored secrets file (`.env` or an environment-scoped equivalent),
outside the web root wherever the host allows it; a *tracked* `.env.example` (or per-key documented
list) carrying only placeholder values. Surfaces: one loader that is the sole place secrets are
parsed; a CLI/test check that scans every tracked file for live values. Behaviour: every consumer
reads through one canonical accessor, never a raw `$_ENV`/`getenv()` call scattered through the
codebase — and that accessor reads `$_ENV`, `getenv()` *and* `$_SERVER`, because a value delivered by
Apache `SetEnv` (how staging's environment path reaches PHP) arrives only in `$_SERVER`: in one
project a required secret was invisible to the one reader that bypassed the accessor while every
other secret resolved fine; a required secret that is absent throws, naming the key and never the
value; the
no-live-secret-in-a-tracked-file check is enforced in the release gate, not merely documented as a
policy.

**env.environments.** Data: one explicit deployment-identity value (e.g. `APP_ENV` naming
local/staging/production) plus the database name/host it opens. Surfaces: a way to ask "which
environment is this, and does it agree with what it opened" — a startup check, a health field, or
both. Behaviour: local, staging and production are distinct databases, never shared even by naming
convention; the routing decision is a pure function of explicit configuration, never an OS sniff or a
hostname guess; unset or ambiguous configuration fails closed to the *safest* target (loopback, no
remote default anywhere), never to a guessed remote server; a stated identity that disagrees with the
schema it actually opened is refused or at minimum reported at error severity.

**env.staging-lock.** Data: none — this is infrastructure, not application state. Surfaces: the
staging vhost/hostname, the host's public address(es), and a private network address (VPN/mesh — e.g.
Tailscale) the vhost is additionally bound to. Behaviour: staging answers *only* on the private
address; the public address refuses at the connection/listener level even when a request correctly
names the staging hostname in its `Host` header (name-based virtual hosting means DNS alone enforces
nothing). The database boundary (staging schema vs. production schema) is a *separate* control from
the network lock — both must hold independently; neither substitutes for the other.

**docs.layout.** The `.docs/` working-document *workflow* (roadmap/plan/task/walkthrough/changelog/
handover/reference, and the rules for writing to them) is owned by the global `CLAUDE.md` §1 — do not
restate it here. What this capability covers is narrower: what the scaffold *lays down* on day one —
`AGENTS.md` at the project root (environments, a deep-reference map pointing into `.docs/reference/*`,
domain invariants), a `CLAUDE.md` that is a one-line pointer (`@AGENTS.md`) so every AI harness reads
one canonical file, and an empty-but-present `.docs/roadmap.md`. Surfaces: the two root files plus the
`.docs/` directory. Behaviour: `AGENTS.md` is the canonical file; `CLAUDE.md` (or any other harness's
entry file) never duplicates its content, only points at it.

**http.deny.** Data: none. Surfaces: a deny rule over dotfiles (`.env`, `.git/`), over any directory
holding CLI-only tooling or shared libraries not meant to be hit directly (a `scripts/`, `includes/`,
or `lib/` that assumes a trusted caller and may open a database connection at `require` time), and
over the migration runner itself. Behaviour: layered — at minimum an application-level rewrite/rule
*and* a server-level (nginx/vhost) directive — because the application-level layer depends on a
specific module being loaded and per-directory config being honoured; if either assumption is false
the layer evaporates with no error. A CLI-only runner (`migrate.php`, `backup.php`, `retention.php`)
additionally carries its **own** `PHP_SAPI` guard as the innermost layer, and the dev router mirrors
the deny so local and production agree — three layers, each failing independently. Verify with a single live request per path, never a burst (a scan
pattern gets the requesting IP banned by the host's own abuse detection).

**http.headers.** Data: none. Surfaces: response headers on every request. Behaviour: a security
baseline (`X-Content-Type-Options: nosniff`, a frame-ancestors/frame-options policy, a referrer
policy, HSTS on https) plus a Content-Security-Policy — report-only is an acceptable first rung, not a
reason to skip it; exactly one emitter for the CSP (see Invariant 20); non-production responses carry
`X-Robots-Tag: noindex`; cache headers differ for revalidate-always assets (JS/CSS/HTML shell) versus
long-lived immutable media.

**release.versioning.** Data: one version constant; if the project has a client-side cache to bust
(a service worker, a versioned asset scheme), a minimum-supported-version floor alongside it.
Surfaces: something that reports the running version — a footer badge, a version endpoint, a health
field. Behaviour: the version bump travels in lockstep with any cache-key constant it gates; the
minimum-version floor can never exceed the current version, or every client on the floor loops
forever between "update" and "still below minimum."

**db.migrations.** Data: a ledger table recording filename (or ordinal), a checksum, and when it
applied. Surfaces: a CLI runner; optionally a read-only status/`--verify` mode. Behaviour: migrations
are additive and idempotent whenever a deploy hook can run them automatically — because the hook runs
*after* the new code is already live, so for some window the new code talks to the old schema; a
statement that can change or destroy existing data takes an explicit, separately-approved path,
never the default deploy flow; a data-risk detector (regex or otherwise) is a backstop that catches
the common case, not the control itself; if two runners could ever fire concurrently against the same
server (two deploy hooks, a manual run beside an automated one), the whole run holds an advisory lock
whose name is scoped to more than just the server (see Invariant 8). A migration that touches a large
or contended table is **rehearsed** before it rides the deploy hook: applied to a copy of the
production schema on the disposable database (see `test.battery`), timed, and run under the
database-bearing suites — the rehearsal is evidence only about the exact server version it ran on,
which is why that version is pinned in CI and in the local rig together.

**db.backups.** Data: a directory outside the document root. Surfaces: a scheduled dump job; a
pre-migration dump triggered by anything about to apply a data-risky change. Behaviour: blank/absent
configuration means the feature is *disabled*, never "guess a path" — a dump holds every password
hash and every piece of PII in the database; if more than one dump stream shares an engine, each uses
a filename prefix disjoint from the others' so their retention windows cannot prune each other's
files; a credential never appears on a subprocess command line (a 0600 defaults/option file instead);
a dump is written under a temporary name and atomically renamed into place only once a completion
marker proves it finished, so a truncated file can never be mistaken for a usable one.

**test.battery.** Data/surfaces: a suite set discovered by globbing a naming convention (never a
hand-maintained list); a CI workflow; if any suites need a real database, a manifest that *declares*
which ones, backstopped by an automated require-graph or similar heuristic for anything undeclared.
Behaviour: the scope of any given run (full vs. a narrower subset) is printed in that run's own
output, because a partial run that looks identical to a full one is how a release ships on
unverified evidence; "this change didn't touch the schema" is never sufficient reason to skip
database-backed suites — the only safe question is whether the change can reach PHP (or the runtime)
at all; a CI rule that skips the expensive job reads changed file *paths*, never commit subjects, and
never applies to the release branch itself.

*The disposable database.* Database-bearing suites run against a **disposable target** — never the
developer's working schema (which holds seeded content the suites would reset) and never anything
reachable from staging or production. Two shapes satisfy this: a throwaway *schema* on the local
instance, created and dropped by the runner (enough for a small project whose suites only need
tables), or a throwaway *instance* — a second server process on its own port with its data directory
under the repository's ignored scratch space, on the exact version production runs — required when
suites rehearse migrations, lock contention, or version-specific behaviour such as collations. With an
instance, the runner refuses any data directory outside the scratch path, so a disposable-target run
physically cannot reach a real database. Its connection details are **process** environment
variables, never `.env` keys, so nothing can leak into a tracked file or an ordinary request; the
consequence is that they do not survive a new shell, and the runner must say loudly when it finds
them absent instead of skipping suites and exiting 0.

*CI.* Three jobs: **scope** decides from changed paths whether the expensive job is needed;
**gate** runs the syntax sweep and the hermetic suites across the supported PHP versions;
**database** installs the pinned server version, builds a throwaway application schema, and runs the
database-bearing suites. Every job carries a timeout. A suite that quietly grows a database dependency
lands in `unclassified` and the gate refuses until someone declares it; a `local_only` entry carries a
written reason. A **disabled** workflow is a recorded state, not an absence: the manifest marks
`test.battery` as `partial` with the reason and the command that restores it, because "CI is off"
must never be something the next session discovers by reading a green local battery as a release.

*Where CI runs — hosted or self-hosted.* The three-job shape is independent of the runner. GitHub's
hosted `ubuntu-latest` is the default; a **self-hosted runner on the deploy VPS** is the alternative
when hosted minutes are the constraint, or — the stronger reason — when the gate should execute on the
*exact runtime production runs* rather than a distro's PHP. **The skill ships the workflow itself —
`assets/ci-workflow.template.yml`** — carrying both runner modes, the path-scoping rule and every trap
below as comments; lay that down and fill in the placeholders rather than copying another project's
file. (One project moved to a self-hosted runner for exactly this reason, and is a working example
of the result.)
The contract the template implements:

- **One workflow, branched on `runner.environment`, not two.** `shivammathur/setup-php` installs via
  apt and needs sudo, so it runs only on `github-hosted`; on `self-hosted` a step prepends the host's
  own PHP to `PATH` instead — but **asserts the build has `pdo_mysql` first** (a host often carries a
  second PHP without the driver, and its failure reads exactly like a database-credentials problem).
  `actions/setup-node` stays on both — it unpacks a tarball into the tool cache and needs no sudo.
  Resolve the PHP path from `${{ matrix.php }}`, never a hardcoded version, or the matrix silently
  tests one version twice while claiming two. `runner.*` is not available in a job-level `env:` block —
  set runner-derived paths from a step via `$RUNNER_TEMP`/`$GITHUB_ENV`, or GitHub rejects the whole
  workflow at dispatch with no line number.
- **The runner is registered per repository; the container daemon can be shared.** Each project gets
  its own runner directory, service and label; a rootless Docker daemon on the host can back several.
  Never add the runner user to the `docker` group (root-equivalence on a box serving other sites);
  keep the runner's `_work` **outside** any vhost root (a checkout that can walk up to a real `.env`
  is a secret-disclosure path); give each project its **own published database port** (two projects
  on one port collide the moment their jobs overlap, and a per-repo runner does one job at a time, so
  overlap is normal); and prune the image cache on a schedule from day one — rootless Docker cannot
  enforce block-I/O limits, so a runaway job degrades every co-hosted site.
- **A self-hosted database container is stricter than a laptop.** It ships `STRICT_TRANS_TABLES`; a
  value silently truncated locally for months becomes a real error on the first CI run. Expect that
  class of finding, and treat it as a bug the gate caught, not CI noise. (A fresh CI database loaded
  from the baseline schema also has *every* migration pending, so the runner needs the same
  data-change allowance the deploy hook is trusted with — never `--baseline`, which records files as
  applied without running them and would skip the very migration under review.)
- **A skipped job still reports success.** A docs-only push legitimately skips `database`, so a green
  tick is not proof the gate ran — require the `database` job specifically in branch protection, and
  check which commit a green tick belongs to (a fast follow-up docs push can cancel the run that
  mattered and leave its own skip showing green).

*The release gate* is three things together, none of which substitutes for another: the full battery
(`scope=full` printed in its own summary), the aggregate audit over the changed files
(`audit_all.py --changed`, the global `asdev-web-audit` suite), and — when the aggregate gate fails — the
delta audit (`audit_delta.py --since main`) that separates findings the change introduced from
pre-existing ones. The per-repository side of that machinery is laid down at scaffold: a
`.auditignore`, an empty `.audit-baseline.json` (reviewed, by-design findings with a written reason
each — one entry per finding, no wildcards), and a Git pre-commit hook that audits the exact staged
index (`run_audit.sh --staged` — the shape `assets/pre-commit.template.sh` installs) rather than one
that refuses any commit from a dirty tree, which blocks legitimate partial commits when another
session's work sits in it — and delegates to the ONE canonical audit copy. The scanners themselves are global and are never copied into a project.

**ops.health.** Data: none required; optionally a heartbeat/last-run table for background jobs whose
silence is otherwise ambiguous (did it run and find nothing, or not run at all?). Surfaces: at
minimum a public liveness endpoint; optionally a token-gated detailed tier. Behaviour: the public tier
returns a status code and, at most, one word — no component list, no version, no error text, because
an anonymous endpoint that enumerates what's unhealthy is reconnaissance; "degraded," publicly, means
"cannot serve requests" and nothing broader — folding a late cron into that verdict corrupts the one
figure an uptime monitor is supposed to measure; any monitoring write (a heartbeat row, a job-run
record) is non-fatal, because recording that something happened must never be able to break the thing
it's recording.

**mail.transport.** Data: a From-address configuration. Surfaces: one send function every outbound
mail goes through. Behaviour: sending is best-effort — a mail failure must never fail the domain
action that triggered it (a signup must succeed even when its welcome email doesn't); outside
production, mail is logged rather than actually sent, so local development and CI never reach a real
inbox; the From address is validated as a single mailbox before use, because it typically gets
interpolated into a raw header block where a stray line break becomes a new header rather than a bad
address.

**seo.core** *(Tier 2)*. Data: none beyond content already in the database; optional per-page
metadata columns (an image, a noindex flag). Surfaces: a generated sitemap (never a hand-maintained
file that drifts from the routes it claims to list), `robots.txt`, per-page title/description/
canonical/Open-Graph/JSON-LD, and a noindex signal for non-production. Behaviour: the crawlable
surface is server-rendered so it works with JavaScript disabled; the sitemap is generated from the
*same* source of truth the router/page map already uses, never a second list; non-production always
emits noindex; canonical-URL construction uses a fixed configured origin, never the request's `Host`
header (which a proxy or an attacker can influence).

## 3. Invariants

1. **Secrets policy must be an enforced check, not a sentence in a doc.** A committed secret is a
   value the audit tooling has never seen, so a text policy stays green forever even while it is being
   violated. One project's tracked `.env.example` was re-committed carrying several live credentials,
   and the shared audit ran green throughout — it had no rule that could ever match a specific secret
   value. The fix was a dedicated secrets check that now runs *first* in the release gate and asserts
   two independent properties: no live `.env` value appears in any tracked file, and every
   credential-shaped key in a tracked template stays blank or placeholder.

2. **An unstated environment must resolve to the safest possible target, never a remote one.**
   One project's early environment resolution fell back to a compiled-in, OS-sniffed default that
   was literally the production server's address, so a developer machine with a truncated `.env`
   connected straight to production and said nothing about it. The fix left exactly one fallback
   anywhere in the code, and it is loopback.

3. **A platform-vs-server distinction can be enforced absolutely only when it is provably inert on
   the side that could be damaged.** One project refuses to boot outright on a Windows host that opens
   the production schema — enforced, not merely reported, *because* the check is Linux-inert by
   construction: no server `.env`, on any real deployment, can ever trigger it. Contrast a sibling
   environment/schema-mismatch check, which stays report-only, because it genuinely could misfire
   against a real, not-yet-migrated server deployment, and a false positive there costs uptime.

4. **A scoped secrets directory, once it exists, is authoritative — never a fallback source.**
   One project's three-environments-one-vhost topology resolves a docroot-scoped secrets directory
   first; an earlier, naive "sibling directory" rule handed staging *production's* `.env` — production
   database, live payment keys — silently, surfacing two steps removed from the cause as an unrelated
   CSRF error on login (because the base URL was now wrong). If a scoped directory exists but its
   `.env` is unreadable, the process refuses to start rather than falling through — falling back would
   mean loading a different environment's secrets, which is the exact hazard being guarded against.

5. **A staging network lock must refuse at the connection level, and must be verified by forcing a
   specific address — never by trusting DNS or a browser.** Moving DNS off the public address changes
   nothing on its own, because name-based virtual hosting means the public IP keeps answering for the
   hostname until it is explicitly taught to refuse; verifying in a browser, once DNS points at the
   private address, shows a working site while the public address happily keeps serving anyone who
   asks for it by name. `curl --resolve <host>:443:<ip>` (with the platform-appropriate binary — on
   Windows, plain `curl` is a PowerShell alias with no `--resolve`; use `curl.exe` explicitly) against
   *both* addresses is the only verification that means anything.

6. **A migration runner that ships schema changes automatically on deploy must treat every migration
   as additive and idempotent, full stop.** In a deploy hook that runs the migrator *after* the new
   code is already live, "new code meets old schema for a few seconds" is the standing condition on
   every deploy, not an edge case to design around.

7. **A data-risk detector is a backstop, never the control.** A regex-based data-risk detector already
   had one false negative in testing: one migration slipped past its `UPDATE` pattern because a `JOIN`
   sat between the table name and the `SET` clause. The actual rule is procedural — a data-risky
   migration needs a human's explicit approval before it deploys — and the detector exists only to
   make the common case hard to get wrong by accident. It errs toward false positives on purpose; a
   false negative is the failure mode that matters.

8. **Advisory-lock names are scoped to the server, not the schema — two databases sharing one MySQL
   instance share the same lock namespace unless a project namespaces it deliberately.** A staging
   deploy once waited fifteen minutes on production's own worker lock, because both environments'
   locks used the same literal name on the same physical server. A bare string literal is the easy
   mistake — the safe pattern is a lock name that incorporates the schema it protects, for example by
   appending the result of `SELECT DATABASE()` to the literal, so the namespace travels with the
   connection rather than living as a second constant that can drift out of sync.

9. **A backup runner refuses to guess a path.** A blank backup-directory configuration disables
   scheduled and pre-migration backups outright, because a dump holds every password hash, every
   remember-me token, and every piece of captured PII in the database — writing one somewhere
   plausible under the document root risks it being directly downloadable.

10. **Two dump streams sharing one engine need disjoint filename prefixes, or their retention windows
    prune each other's files.** One project's single dump function is called by both the pre-migration
    safety dump and a scheduled cron backup; the prefix is part of each stream's own prune glob
    specifically so neither can rotate the other's history away.

11. **A test battery's scope must be printed in its own output, or a partial run is
    indistinguishable from a full one.** One project's battery runner prints `scope=full` or
    `scope=hermetic` in its summary line precisely because a run that silently skipped suites (an
    unconfigured disposable database, in one real incident, silently skipped nineteen suites and still
    exited 0) is otherwise unrecognisable from a genuinely green release.

12. **Never widen "this change didn't touch the schema" into "skip the database-backed suites."**
    In one project, dozens of database-bearing suites cover row locks, races, a state machine,
    scheduling, and account provisioning — almost none of which is DDL. The only safe question is
    whether the change can reach the runtime at all, not whether it edited a `CREATE TABLE`.

13. **Declare which suites need a database explicitly; use a require-graph (or similar) heuristic only
    as a fail-closed backstop for anything undeclared.** In one project, a handful of suites took a
    connection string from the environment directly instead of going through the shared database
    bootstrap, so a require-graph heuristic classified them "hermetic," CI ran them with no database
    configured, and every one passed only by coincidentally matching a "not configured, so skip"
    signature — an entire category of concurrency and lock-contention coverage ran unexercised while
    the gate stayed green the whole time.

14. **A CI cost-skipping rule reads changed file paths, never commit subjects, and never applies to
    the release branch.** One commit titled as a docs-only change correctly still ran the expensive
    job because it also touched a secrets-template file — a rule that inspected the subject line
    alone would have skipped it wrongly.

15. **A health endpoint needs two tiers, and an anonymous "detailed" tier is reconnaissance, not
    observability.** The public answer is a status code and one word; the detailed tier — component
    states, job freshness, deploy identity — is gated behind a credential, reusing an *existing* one
    rather than minting a new secret to rotate.

16. **"Degraded," in the public tier, must mean only "cannot serve requests."** Folding a late cron
    into that verdict would make the uptime figure measure something other than uptime, and would
    page someone at 3 a.m. because a backup ran an hour late rather than because the site is down.

17. **A monitoring write must be non-fatal.** A heartbeat recorder should swallow its own failures for
    the same reason a webhook enqueuer does: recording that a job ran must never be able to break the
    job it's recording, and this holds even during the brief post-deploy window when the heartbeat
    table itself might not exist yet.

18. **`never`/`disabled` job states are not alarms.** A fresh install, or a feature the operator has
    deliberately left off, must not report "degraded" from day one — a monitor that cries wolf
    immediately is a monitor nobody keeps watching.

19. **Mail sending is best-effort everywhere, and non-production never reaches a real inbox.** One
    reference shape logs the message instead of actually sending outside production, so local
    development, CI and staging never send to a real address; a caller treats the return value as
    telemetry, never a gate on the action that triggered it. Skipping this is a real, easy-to-miss
    gap: a project whose mail sender has no environment check at all will email a real inbox the
    first time a tester registers on staging with a real address, or an admin answers a ticket there
    — so verify the environment check exists and is actually exercised, not merely assumed.

20. **A Content-Security-Policy has exactly one correct emitter.** Adding a second CSP header at the
    infrastructure layer does not add defense in depth — two policies are enforced as an
    *intersection*, and an inline bootstrap script written for one policy cannot simultaneously
    satisfy an independently-authored second one. If the project runs a service worker that replays a
    cached shell, compute the CSP's script hashes per request rather than as a precomputed constant: a
    hash baked in against a CRLF Windows working tree will not match the LF bytes actually served from
    a Linux production checkout.

21. **`NULL`/`NOT NULL` must be spelled explicitly on every `TIMESTAMP` column.** Left unqualified,
    MySQL infers nullability from `explicit_defaults_for_timestamp`, which is a server setting — two
    servers running byte-identical `CREATE TABLE` statements can disagree. This split more than a
    dozen columns across one project's two databases with a clean migration ledger the entire time,
    because the columns were never *a migration* to begin with — only a field-by-field schema-snapshot
    comparison caught it.

22. **Server deny directives need at least two independent layers, ideally three.** An
    application-level rewrite deny depends on a rewrite module being loaded; a per-directory `Require
    all denied` depends on the web server honouring per-directory config at all; a server/vhost-level
    directive depends on neither. Verify by deliberately disabling the layer above and confirming the
    one below still holds — a suite that falsifies each layer this way, rather than trusting that it
    works, is the only way to know the redundancy is real.

23. **SEO surfaces must reuse the exact map the routes are built from, never a second hand-maintained
    list.** One sitemap generator used to recover its own page list by walking the front controller's
    source at request time, which broke silently the day a page title happened to use double quotes.
    The fix moved the map into one file both the router and the sitemap generator load, so there is
    nothing left that can drift.

24. **Non-production must send `noindex` from a response header, not rely on `robots.txt` alone.**
    `robots.txt` governs crawling, not indexing, and it is typically a static file identical across
    every environment; a header covers every server-rendered surface at once — including error and
    auth responses, which is disproportionately what a crawler meets first on a freshly stood-up
    staging host — rather than a per-route list someone has to keep current. Watch for the header
    silently failing to apply on an error/redirect response specifically: an internal redirect renames
    environment variables with a prefix across that boundary, and a condition written against the
    plain name alone stops matching exactly on the responses most worth protecting.

25. **A disposable database must be started detached, and its absence must be recognised before a
    red battery is believed.** An instance started with `nohup` from a tool call is reaped when that
    call's job ends — the process vanishes, its log stays empty, and the next battery reports a
    couple dozen suites "provisioned but NOT RUNNING", which reads exactly like a mass regression. It
    cost one entirely invalid run in a real project. Start it with PowerShell `Start-Process` (or the
    platform's equivalent of a detached service), confirm `SELECT VERSION()` before trusting any red
    result, and never restart it mid-run — later suites pick the instance up and the mixed result is
    invalid in both directions.

26. **Connection details held only in process environment are a feature with a failure mode, and the
    runner owns the failure mode.** A handful of disposable-database connection variables are
    deliberately not `.env` keys, so a fresh shell reports "disposable database not configured" — and
    the battery once skipped nineteen suites on that signal and still exited 0. A port being open is
    not configuration. The runner prints the skip as a scope change (Invariant 11) and a marker table
    inside the disposable schema lets the values be recovered rather than guessed.

27. **Two suites that reset one disposable database never run concurrently.** Two agents resetting the
    same instance corrupt both runs and produce failures indistinguishable from real regressions; an
    interrupted index mutation is not self-healing. Single-writer applies to the test database exactly
    as it applies to a shared file.

28. **CI timeouts are load-bearing, and the database version in CI is the local rig's version.**
    Three runs in one project hung without a timeout and rode GitHub's 360-minute default, burning
    over a thousand minutes — well over half a month's allowance on a private repository; the scoping
    job is now capped at 5 minutes, the gate job at 15, the database job at 30. The database server is
    pinned to an exact patch version from the vendor archive — not the distribution's older package
    (which predated the collations the schema uses) and not a rolling series — because a rehearsal is
    evidence only about the version it rehearsed on, and bumping it means bumping the local rig and
    the runner constant together.

## 4. Reference implementations

*Pointers into the author's own repositories live in the optional `local/pointers/<name>.md` overlay,
which is not shared. The contract in §2 and the invariants in §3 stand on their own: they say what to
build and why, not where one team's copy happens to sit.*

## 5. Decision points

1. **Migration approval model.** Default: an automated, data-risk-detector-backstopped shape for any
   project whose deploy hook runs migrations unattended. A human-approval-as-policy shape is
   acceptable only when every schema change is already gated by a human step regardless of what the
   runner itself would allow.
2. **Backup mechanism.** Default: a `mysqldump` subprocess when a shell subprocess is acceptable in
   the deploy environment — it is full-fidelity and restores everything. Use an app-level JSON export
   over an explicit content-table allowlist when a subprocess isn't available or wanted, or when
   "content only, never credentials" is itself the desired property, independent of schema shape.
3. **Health-endpoint credential.** Default: reuse an existing token-gated read-only credential if the
   project already has one; mint one dedicated credential otherwise. Never gate the detailed tier
   behind full user/session auth — an uptime monitor should never need to hold a session.
4. **CSP enforcement ladder.** Default: ship report-only first and flip to enforcing only after a
   measured, zero-violation sweep across every real surface, for any project inheriting existing pages
   with unaudited inline scripts or styles. A straight enforce-from-day-one boolean is fine only for a
   fresh project with no legacy inline content to discover violations in.
5. **Where the CSP is computed.** Default: per-request hashing the moment a service worker or a
   Windows-dev/Linux-prod line-ending mismatch is in play (Invariant 20). A precomputed constant is
   safe only for a project with no service worker and a committed line-ending pin on every file that
   constant is computed from.
6. **Scheduled backups vs. host-level backup only.** Default: add an application-level scheduled dump
   whenever the database holds anything the host's own backup cadence wouldn't recover fast enough
   (a hosting panel's nightly full-VPS backup is disaster recovery, not a six-hourly RPO). If the host-level
   backup is judged sufficient for a given project, record that explicitly in the platform manifest
   rather than leaving `db.backups` silently undone.
7. **Disposable database: instance or schema.** Default for a new project: a throwaway *schema* on
   the local instance, created and dropped by the runner, with the connection details still held
   only in process environment. Escalate to a second *instance* (own port, data directory under the
   repository's ignored scratch path, the exact production version, the data-directory guard) the
   moment a suite rehearses a migration, exercises row or advisory locks under contention, or
   depends on server-version behaviour such as collations — and record the escalation in the
   manifest, because from then on CI must pin the same version.
8. **CI enabled or disabled.** Default: enabled, with `database` conditional on changed paths. If the
   owner disables the workflow (cost, a broken runner, a migration of the CI host), the manifest row
   for `test.battery` drops to `partial` with the reason and the exact `gh workflow enable` command,
   and the local full battery plus a live staging exercise are named as the interim gate.
9. **CI runner: hosted or self-hosted.** Default: GitHub-hosted `ubuntu-latest`. Move to a
   self-hosted runner on the deploy VPS when hosted minutes are the binding constraint, or when the
   gate must run on the *same PHP build production runs* (a distro's PHP can differ from a host's
   managed PHP in exactly the extension — `pdo_mysql` — the database suites need). It is one workflow
   either way, branched on `runner.environment`; the operational contract (per-repo runner, shared
   rootless daemon, per-project database port, `_work` outside any vhost, scheduled prune) is in §2
   under `test.battery`.

## 6. Gaps and design briefs

Every capability in this file is buildable straight from the contract above — there is no pure gap to
brief here. The one soft spot worth naming: `env.staging-lock` verification is typically a manual,
human-run `curl --resolve` check, not an automated assertion in a CI workflow or test battery. A
future enhancement — not required to satisfy this capability today — would be a scheduled or
release-gate check that performs the same two `--resolve` probes and fails loudly if the public
address ever starts answering again.

## 7. Manifest rows

| id | tier | done means |
|---|---|---|
| `env.secrets` | 0 | git-ignored secrets file + tracked placeholder-only example, with an enforced test that no live value ever reaches a tracked file |
| `env.environments` | 0 | local/staging/production resolve to distinct databases via one explicit key that fails closed to loopback; no OS or hostname sniffing anywhere |
| `env.staging-lock` | 0 | staging answers only on a private network address; the public address refuses at the connection level even with a correctly-named `Host` header, verified by forcing the address |
| `docs.layout` | 0 | `AGENTS.md` (environments, deep-reference map, invariants) + a one-line `CLAUDE.md` pointer + a present `.docs/roadmap.md`, per the global `.docs/` workflow |
| `http.deny` | 0 | non-public directories and the migration runner refuse over HTTP at two or more independent layers, each verified by disabling the layer above it |
| `http.headers` | 0 | baseline security headers + a CSP (report-only is acceptable initially) on every response; non-production sends `X-Robots-Tag: noindex` |
| `release.versioning` | 0 | one version constant bumped in lockstep with any client cache key; a minimum-version floor that can never exceed the current version |
| `db.migrations` | 0 | an idempotent, ordered, ledgered migration runner; any statement that can touch existing data takes an explicit, separately-approved path |
| `db.backups` | 0 | a scheduled dump outside the docroot with bounded, disjoint-prefix retention — or an explicit, recorded decision that host-level backup covers it instead |
| `test.battery` | 0 | a globbed suite set with a three-job CI workflow (timeouts, pinned server version, path-scoped `database` job) wired up and enabled; every run's scope printed in its own output; database-bearing suites declared and run only against a disposable target whose configuration lives in process environment; `.auditignore`, `.audit-baseline.json` and the delegating pre-commit hook in place |
| `ops.health` | 0 | a public liveness endpoint that distinguishes up from down with no leaked detail beyond that |
| `mail.transport` | 0 | one `send()` function every outbound mail goes through; non-production never reaches a real inbox |
| `seo.core` | 2 | a generated (never hand-maintained) sitemap, `robots.txt`, per-page metadata, and non-production noindex, all sourced from the app's own route/page map |
