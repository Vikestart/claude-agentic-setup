# Billing — platform contract

*Part of the `asdev-blueprints` skill. Tier 3. Read this before scaffolding, auditing, or building any of: `billing.provider`, `billing.plans`, `billing.webhooks`, `billing.entitlements`, `billing.referrals`.*

## Contents

1. Scope and timing · 2. The contract (provider · plans · checkout · webhooks · entitlements · customer surface · refunds
· referrals) · 3. Invariants · 4. Reference implementations · 5. Decision points · 6. Gaps · 7. Manifest rows

## 1. Scope and timing

Tier 3: **where applicable** — only when the product sells something. Nothing here belongs in a scaffold. Two things
about the *timing* are counter-intuitive:

- **The provider decision is cheapest before the first subscriber and gets rapidly more expensive.** Subscriptions cannot
  be transferred between merchants of record — the MoR holds the payment mandate, so a later switch forces every
  subscriber to re-enter a card, which is churn. A provider migration is affordable exactly while the subscriber count is
  zero. Make the call while that is still true.
- **`legal.pages` (Tier 1) is a hard prerequisite.** A merchant of record vets the business before approving the account,
  and domain verification loads `/terms`, `/privacy`, `/refund` and `/pricing` with a crawler that does not run
  JavaScript — so the server-rendered pricing page is on the *billing* critical path even though the page itself belongs
  to [privacy-legal.md](privacy-legal.md) §2.5.

Also out of scope: the policy↔code reconciliation rule (privacy-legal.md §2.6 — and the payment provider is its classic
case, because the Privacy Policy names the processor, so choosing or changing one is a policy edit due in the same phase
as the code); retention and pseudonymisation of stored billing events (privacy-legal.md §2.3–2.4); admin user management
and the audit log (`admin.md`); reward notifications (`notifications.md`); rate limiting and sessions (`identity.md`).

## 2. The contract

Architecture-agnostic. "Endpoint" means a routable action in whatever shape the project uses.

### 2.1 `billing.provider`

One interface, one adapter per provider, one factory. Five methods cover everything two independent implementations
needed:

```php
interface PaymentInterface {
    public function isLive(): bool;
    public function createCheckoutLink(int $userId, string $email, string $returnUrl, array $plan): string;
    public function createPortalLink(int $userId, string $returnUrl): string;
    public function handleWebhook(string $payload, string $sigHeader): bool;
    public function webhookSignatureFromRequest(): string;
}
```

- **Checkout keys off *our* user id.** The provider learns its own customer/subscription ids from the webhook, so no
  provider-specific pre-create step leaks into the controller and no provider id is ever client-supplied.
- **REST over cURL, JSON in and out. No SDK, no package.** Every provider's API is a handful of endpoints; an SDK is a
  dependency, a build step and a supply-chain surface for no benefit.
- **The factory's decision is a pure function** of `(provider name, key present?, is production?)` returning
  `live | mock | unavailable`. Split it out from construction so it can be tested directly — driving construction instead
  means defining configuration constants in a worker process, and the real config loader wins that fight.
- **Selection is by NAME, not key presence.** A stale `PAYMENT_PROVIDER=stripe` with a valid live key for another
  provider present must **refuse**, not quietly sell through whichever provider happens to be configured.
- **Production never falls back to the sandbox.** An unresolvable selection in production returns an explicit
  *unavailable* adapter: not live, no checkout or portal URL, webhooks refused, one log line per request, and **503**
  from the endpoints — our fault, and visible to uptime checks. Outside production the keyless mock is unchanged.
- **One adapter at a time; delete the others.** Not archive — an adapter reachable from configuration is executable code,
  and a partly-correct billing adapter is worse than none because it *looks* like a supported option.
- **The API base URL defaults to the sandbox**, so a half-configured environment cannot take real money. Sandbox keys on
  local and staging, live keys **only** in production's secret file, and the health/`me` endpoint reports `live | mock`.

### 2.2 `billing.plans`

**Data.** A `plans` table where **`code` and duration-in-months are identity**, and everything else is configuration:
display name, `price_cents`, `currency`, `sort`, `is_active`, and one nullable provider price-id column per provider.

**Surfaces.** One reader used by *all three* consumers — the API, the pricing page, the admin editor — so prices cannot differ.

- **Derived fields are derived**: per-month price and "save X%" are computed at read time, never stored. Storing them
  means an admin editing one price leaves a stale saving badge.
- **A hardcoded fallback list** mirrors the seed, and the reader falls back to it on any database error. The pricing page
  is server-rendered, must work with JS off, and is the page the provider's domain review loads — slightly stale numbers
  beat a 500.
- **A duration with no provider price id is `configured: false`** and is hidden from the pricing page and the picker, so
  a plan cannot be half-sold. An inactive or unknown code must never reach a provider: resolve it to a row first.
- **An environment-variable price id is a fallback for the base monthly plan only.** Letting another duration fall back
  to it bills a monthly rate for a year.
- **Free-tier caps are read live from settings by the copy that promises them**, so promise and enforcement cannot drift.
  Never hardcode "3 free projects" in marketing copy while a setting owns the gate.

### 2.3 Checkout

1. Client asks the server to start a checkout for a plan code.
2. Server gates: authenticated; an admin `upgrades_enabled` switch (the real gate — hiding the button proves nothing, a
   client can POST directly); the plan resolves; the account has an email and is not a test account; billing is available
   (else 503); and **no active subscription already exists** (else 409, pointing at the portal).
3. Server creates the provider-side object with **our user id in the provider's custom-data field** — the mapping every
   subsequent webhook uses — and returns a URL; the client navigates or opens the overlay.
4. Two valid shapes: an **overlay on a page of our own** (better UX; needs the provider's script and a CSP allowance
   scoped to that route), or a **fully hosted redirect** (a one-line change of target). A provider may *require* a
   verified page on your domain regardless — dunning and update-payment-method emails point at it — so build that page
   either way, and keep it **outside the SPA**.

### 2.4 `billing.webhooks`

```
read bounded body ─► verify signature over EXACTLY those bytes ─► derive idempotency key + minimised
record from the SAME string ─► INSERT durably ──┬── failed → 5xx, do NOT acknowledge
                                                └── succeeded → 200
                                                       │
                        domain work runs inline (optimisation) and again from a retry sweep
```

**Why.** One pre-inbox handler had **three separate ways to hand the provider a 200 for work that never happened**: the
audit insert failed and it continued anyway; the entitlement update threw inside a swallowing `try/catch` and it still
acked; or the process died between the two. Each is a customer who paid and did not get what they paid for — and a 200
tells the provider never to send it again.

**Durability, then acknowledgement.**
- The only thing that earns a 200 is the event being **durable**. Everything before that answers 5xx so the provider
  redelivers; everything after is retryable work.
- **Idempotency key = the provider's own event id**, stored `UNIQUE`. A body hash is a fallback only for a provider that
  sends no event id — it breaks the moment any envelope field differs on redelivery.
- **The accepted event-id length must equal the storing column's width**, asserted by a test. A pattern that accepted 84
  characters into a `VARCHAR(64)` truncates silently without strict SQL mode, so two distinct ids sharing a prefix
  collide on the unique key and the second real event is acked as a duplicate and never applied — or throws on a strict
  box and loops forever. Reject an over-long id loudly and audit it at full width instead.
- **Only a collision on the dedupe key itself means "already processed."** Any other constraint violation stays retryable.
- **Capture the audit row's identity at insert** (`lastInsertId`). Re-finding it later by `(provider, event_id)` silently
  matches nothing whenever the stored value differs from the string in hand — exactly what truncation produces — and the
  row then reports "not applied" for an entitlement change that was made.
- **A `NULL` state means "ingested before the state machine existed", never "work to retry."** Assert it as behaviour: a
  sweep treating `NULL` as pending replays every historical event the first time it runs.

**Signature verification.**
- Read the body through **one bounded reader, before the HMAC and before any parsing** — this endpoint is reachable
  pre-authentication, which makes the ceiling matter more, not less. Verify with a constant-time compare over exactly
  those bytes. The **stored** record is a privacy-minimised *transform* of that verified string
  ([privacy-legal.md](privacy-legal.md) §2.4), never a different string and never the raw body.
- Accept **every** signature candidate in the header — providers ship multiple while rotating secrets. **No configured
  secret ⇒ refuse**: accepting an unverified subscription event is worse than dropping it.
- **Timestamp tolerance generous enough for clock drift, tight enough to defeat replay.** SDK defaults of ~5 seconds
  mean a drifted server clock silently rejects *every* webhook, and the symptom is "subscriptions stopped working" with
  no error surface. 60 seconds is a good shipped default (`WEBHOOK_TOLERANCE = 60`); 5 minutes is defensible too. Some
  providers send no timestamp at all and authenticate the body alone, which is a replay window you have to close some
  other way. Decide per provider, and write the number down; see §5.
- The webhook boundary is **cookie-free and CSRF-exempt by construction** — it must not load the session-bearing
  request-initialisation path, and must not be reachable by a browser form.

**The retry state machine.**

```
received ──claim──► processing ──► processed          (terminal, succeeded)
                        │
                        ├──────► failed               (retryable; next_attempt_at = backoff)
                        │           └──claim──► processing …
                        └──────► dead                 (terminal: attempts exhausted, or unreplayable)
```

- **Claiming is one conditional `UPDATE`** whose `rowCount() === 1` is the only honest "did I win". Two concurrent
  deliveries both run it; the database serialises them and the loser matches zero rows.
- Bounded attempts with a backoff table; a distinct `dead` state so the dead letter is an indexed lookup rather than a
  filter someone forgets. Expose dead-letter metrics and a requeue action to admins; a lease timestamp makes a crashed
  handler's row reclaimable; a sweep drains whatever the inline attempt did not finish.
- **At-least-once with idempotent effects** is the honest claim, not exactly-once. What converges exactly once is the
  *outcome* — one comp month, one final subscription state — not the number of handler runs.

**Ordering and concurrency.**
- Order by the **provider's own version marker for the resource** (`updated_at` on the subscription, `occurred_at` on
  the event). Your ingestion timestamp is wrong by construction — two deliveries the network reorders get ingestion
  stamps in arrival order, i.e. exactly the wrong order. The resource's *creation* time is identical on every event and
  can never order two of them.
- **Scope the watermark by ACCOUNT, not by subscription** — per-subscription scoping misses cancel-A-then-buy-B: A's
  terminal event is genuinely the newest thing the provider has ever said about that account, so it sails through a
  watermark and overwrites B, costing the customer up to a full renewal cycle of access. The watermark alone only closes
  the *reordered* half of that, so add a second check: since the account row holds exactly one subscription, an event
  about a subscription the account has moved on from may only take the mirror when it reports that one as live.
- **Serialise per account.** Both checks are read-then-write and nothing else serialises two handlers for one account —
  the claim is per-row, the worker lock only excludes other worker ticks, and the webhook takes no lock. Take a per-user
  advisory lock **before** the claim and hold it past the terminal stamp. Measured before the fix in one project: 25 of
  60 barrier-released trials ended on the stale state.
- If you lock rows instead, **lock by primary key in ascending order, and only by primary key.** An `OR`-query with
  `FOR UPDATE` is served as a full clustered-index scan, and `FOR UPDATE` locks every row *examined* — so one
  subscription webhook held an exclusive lock on the entire users table for its transaction's life, and every login,
  invite and admin action queued behind it (measured with a second connection and a short lock-wait timeout). An index
  does not reliably fix it: the optimiser replans the `OR` as an index merge only sometimes, on the same schema minutes
  apart. `id IN (…)` is a primary-key lookup structurally, at any statistics, and ascending PK across every writer is
  what makes a deadlock cycle impossible. Use **READ COMMITTED** if your engine defaults higher: a post-lock re-check
  cannot see a concurrent commit under repeatable read, so the check is decorative.

**Non-production mock completion.** An authenticated, environment-gated endpoint may complete a mock purchase for the
*logged-in* user — never through the webhook, because a forgeable webhook upgrade path is a free-Pro button. Two
conditions, both required: **not production**, and **the database is not the production database** — the second is what
actually protects you, since a flag alone is worthless if staging points at production's data. ⚠️ The second condition is
the one that gets skipped: a gate that checks the environment flag and leans on the environment split to keep staging off
production's data is one misconfigured config file away from being a free-upgrade button on real accounts — see §6. Apply
the same gates as the live path (upgrades switch, plan resolution), and write the same audit row a live webhook would.

### 2.5 `billing.entitlements`

**Server-side only.** A client-side `isPro` flag is chrome. Every paid capability is gated at the write that would use it.

**Source of truth:** the subscription mirror on the account (provider, customer id, subscription id, price id, status,
renews-at, ends-at) **plus** manual grants with an expiry.

- **The manual-grant invariant, which protects paying customers:** the manual expiry column is set *only* by an admin
  grant; the provider webhook *always* clears it; and lazy expiry only downgrades when there is no provider subscription
  id. So expiry can never drop a real subscriber, which is what lets it run without a cron. Design it this way from the start.
- **Lazy expiry, not a scheduled job:** self-heal the stored tier when the account is loaded for authentication;
  non-fatal, because a write failure there must never break login. Provide **one SQL predicate** for "effectively paid
  right now" for every query reading *someone else's* tier (branding, an ingest cap, analytics), where it has not run.
- **The expiry comparison obeys the ONE CLOCK rule.** An expiry written with the application's clock and read back with
  the database's — or the reverse — is off by the timezone offset in whichever direction hurts: it either cuts a paying
  customer off early or hands out free hours. Write it and compare it with the same clock, and make it the database's.
- **Resolve the payer per resource when teams exist.** Entitlement follows the **resource**, not the caller: a
  personally-free teammate gets paid features on a paid workspace's resource. The same resolution drives every cap,
  branding decision and usage ledger. Team-only capabilities additionally check the plan *family* — a personal plan must
  not buy seats.
- **A downgrade never deletes anything.** It refuses *new* work above the free cap; deleting a lapsed customer's content
  is a support incident and probably a legal one. Free-tier caps are enforced at the ingest/creation path, counted per
  payer across everything they own, and read from a setting the marketing copy also reads. Comped accounts count as
  members in head counts and are **excluded from revenue estimates** — they are $0.
- Match the entitlement predicate to the **provider's cancel semantics**. Some flip to `cancelled` immediately and rely
  on an end date to keep access alive; others keep `active` with a scheduled change and only flip at period end. Getting
  this wrong either cuts a paying customer off early or gives away a month. A `past_due` grace usually keeps access while
  the provider dunns; when it gives up it sends the terminal event.

### 2.6 The customer-facing surface, and refunds

One page showing current tier, plan and price, renewal or end date, cancel, update payment method, invoices. Cancel /
payment method / invoices all route to the **provider's hosted portal** — do not rebuild them; portal session URLs are
**single-use: mint on demand, never store**. Surface the upgrade path for free accounts, and when the upgrades switch is
off say so rather than showing a button that 403s.

The refund policy is a legal page (privacy-legal.md §2.5) stating the window, how often it may be used, how
digital-content delivery interacts with statutory withdrawal rights, how to request one, and what cancelling does to
access already paid for. The refund executes at the provider; the resulting event arrives as a webhook and moves the
mirror through the normal path. Decide explicitly whether a refund revokes access immediately or at period end, and make
the entitlement predicate implement that decision rather than leaving it to whichever status the provider sends.

### 2.7 `billing.referrals`

**Data.** A `referrals` row per relationship: referrer, referee (**`UNIQUE`** — a person can only ever be attributed
once), the code used, status, a `reward_granted` flag, created-at and qualified-at. Plus a `referral_code` on the account
and a `referred_by` pointer.

- **Code generation** from an unambiguous alphabet (no `O`/`0`, no `I`/`1`), assigned lazily on first view, unique with a
  bounded retry on collision. **Attribution**: capture `?ref=CODE` at landing into client storage, send it with the
  sign-up, resolve it **server-side**. An unknown code or a self-referral is a silent no-op; the write is `INSERT IGNORE`
  + `SET referred_by = ? WHERE referred_by IS NULL`, so it is once-only even under a double submit; and a storage read
  that throws must not abort the registration.
- **The reward fires on the friend's FIRST PAID INVOICE, not at sign-up** — a sign-up-time reward is free to farm with
  disposable email addresses — and credit accrues from `max(existing credit, now)` so it never shortens an existing one.
- **The grant is a compare-and-swap whose result is checked.** One implementation granted the days *first* and then ran
  `UPDATE … WHERE reward_granted = 0` without reading `rowCount()` — so two concurrent payment events both read `0`, both
  added a month, and only the second's update matched nothing, silently. The order is: `SELECT … FOR UPDATE` inside the
  transaction, claim with the CAS, require `rowCount() === 1`, and only the winner writes the credit, in that transaction.
- **The grant reports three distinct outcomes**: `granted`, `nothing to grant` (no pending referral, or a racer won), and
  `database failed — retry`. A `void` function that swallows the third into a log makes a lost reward indistinguishable
  from "there was nothing to give", and the webhook then acknowledges it.
- **Anti-abuse**: refuse self-referral; refuse when the two accounts share a payment instrument; cap stackable free
  months per referrer per period; expire an unconverted attribution after a window; claw back on a refund or chargeback
  inside the window. Notify the referrer through the project's notification seam — best-effort, never rolling back the
  billing write.

## 3. Invariants

Each rule, then the reasoning that produced it.

1. **Only durability earns a 200.** Three distinct failure paths in one handler used to ack work that never happened. A
   webhook 200 is a promise never to resend; make it only when the event is on disk.

2. **Idempotency is the provider's event id, stored `UNIQUE`, and the accepted id length equals the column width.**
   Truncation into a narrower column makes two real events collide and the second is acked as a duplicate — on the
   revenue path, silently. Assert the constant against the real column in a test so the two cannot drift.

3. **Capture the audit row's primary key at insert; never re-find it by the provider key.** A primary key cannot drift
   from itself. Re-finding removed the whole class of "the row says not applied for a change that was applied".

4. **Order by the provider's own version marker, scoped by account, plus a current-plan check.** Ingestion time orders
   reordered deliveries backwards; resource creation time cannot order anything; per-subscription scoping lets a
   cancelled plan's terminal event overwrite the plan the customer is currently paying for.

5. **Serialise handlers per account with an advisory lock taken before the claim; if you lock rows instead, lock by
   primary key, ascending, and never with an `OR`-query.** The ordering checks are read-then-write and nothing else
   serialises two handlers for one account — measured, 25 of 60 concurrent trials ended on the stale state, and a
   provider redelivering after an outage sends several events for one account at once. And `FOR UPDATE` locks every row
   *examined*, so an `OR`-query served as a clustered-index scan locked the entire users table and every login queued
   behind it; an index does not reliably fix it, because the optimiser flips plans on the same schema.

6. **`NULL` state means historical, never pending.** A retry sweep treating `NULL` as work would replay every event ever
   ingested, on the production database, the first time it runs.

7. **Provider selection is by name, fails closed in production, never falls back to the sandbox — and unsupported
   adapters are deleted, not archived.** One factory returned the mock for any unresolved selection, production included.
   It never granted free Pro — the mock endpoint refuses in production — it sent paying customers to an internal sandbox
   page that then refused, so **the store silently stopped selling while the deployment looked healthy**. Answer 503,
   not a 4xx: it is our fault and uptime checks should see it. And anything selectable from configuration is executable
   code: a partly-correct adapter is worse than none because it looks supported.

8. **Mock completion requires not-production *and* a non-production database, and is never the webhook.** The
    environment flag alone is worthless if staging points at production's data — an authenticated non-prod endpoint then
    becomes a free-upgrade button on real accounts, and a gate that checks only the flag is trusting a deployment
    convention to protect real money. And a forgeable webhook upgrade is the one thing worse than no sandbox.

9. **The webhook boundary is cookie-free and does not load the session-bearing init path; the body is bounded before the
   HMAC; the signature covers exactly the bytes read; the timestamp tolerance is a deliberate number.** It is an HMAC
   boundary, not a browser one — sessions bring CSRF and maintenance gates that have no meaning here and pull a large
   dependency graph into a path that must also be replayable from CLI. A ceiling applied *after* the signature check, or
   a signature checked over a different string than the one the stored record derives from, both mean the row you keep
   is not the row you verified. And SDK-default tolerances of ~5 seconds mean a drifted clock rejects every webhook with
   no error surface — the symptom is "subscriptions stopped working".

10. **Manual grants own the expiry column; the webhook always clears it; expiry only downgrades when there is no
    provider subscription.** This trio lets lazy expiry run everywhere without ever dropping a paying customer, and
    removes the need for a cron. The expiry itself is written and compared by one clock — the database's — or the
    timezone offset silently buys or sells hours of paid access.

11. **The paywall is enforced server-side, at the write.** Hiding the button proves nothing — a client can call the
    endpoint directly. Check ownership *first* so "not yours" stays a 404 and only an insufficient tier is a 403.

12. **Entitlement follows the resource, not the caller.** With teams the payer is the workspace owner. Resolve the payer
    once, in the access-context helper, and make every cap, branding decision and usage ledger read that same value —
    otherwise they drift apart one feature at a time.

13. **A downgrade refuses new work and never deletes.** Deleting a lapsed customer's content is a support incident;
    refusing new recordings above the free cap is the enforcement.

14. **Plan code and duration are identity; price and provider ids are configuration; derived figures are derived and the
    pricing page has a coded fallback.** Adding a duration then never touches a provider adapter, and an unconfigured
    duration is hidden rather than half-sold — never let a non-monthly duration fall back to the monthly price id. A
    stored "save 17%" goes stale the moment a price is edited, and the one page a provider's domain review loads must
    not be able to 500.

15. **A referral reward is granted once, by a CAS whose `rowCount()` is checked, and reported in three outcomes.** One
    implementation's CAS was decorative — it granted first and never read the result, so a webhook retry racing its
    original delivery paid two free months. The three-outcome return is what lets the inbox retry a database failure
    instead of acking a lost reward.

16. **The reward fires on the first paid invoice, never at sign-up.** Sign-up rewards are farmable with disposable
    addresses; a paid invoice costs the abuser real money.

17. **The billing audit outlives the account; analytics writes on the billing path are non-fatal, entitlement writes are
    not.** The audit's foreign key nulls the user rather than cascading, keeping membership analytics and chargeback
    defence intact after a deletion — and it is exactly the row privacy-legal.md requires to be pseudonymised and
    minimised. Losing a chart row must never fail a webhook the provider would retry; losing an entitlement write must.

## 4. Reference implementations

*Pointers into the author's own repositories live in the optional `local/pointers/<name>.md` overlay,
which is not shared. The contract in §2 and the invariants in §3 stand on their own: they say what to
build and why, not where one team's copy happens to sit.*

## 5. Decision points

| Decision | Default | Notes |
|---|---|---|
| Provider | **Paddle Billing** (merchant of record) | Deepest tax-jurisdiction coverage at a comparable all-in rate; it is seller of record for VAT/sales tax. Re-verify the current rates before committing — they move, and a comparison more than a few months old is stale. |
| Plan durations | **Monthly + annual**, quarterly optional | The economics matter more than the provider: at a low monthly price the fixed per-transaction fee alone can be ~10%, so moving customers to annual moves the effective rate several times further than switching provider does. |
| Checkout shape | **Overlay on a verified page of our own** | The provider is likely to require that page for dunning and update-payment-method emails anyway; a hosted redirect is then a one-line fallback, not a cheaper design. |
| Idempotency key | **Provider `event_id`**, body hash only as fallback | A body hash breaks when any envelope field differs on redelivery. |
| Signature tolerance | **60 s** shipped; 5 min defensible | Not the SDK-default seconds; pick per provider and write the number down. |
| Retry ceiling | **~6 attempts over ~4.5 hours** | Long enough to ride out a database restart, short enough that an operator sees a genuinely broken event the same working day. |
| Comp / manual grants | **A separate expiry column the webhook always clears** | The invariant that keeps expiry from ever dropping a subscriber. |
| Downgrade behaviour | **Refuse new work; never delete** | Deleting a lapsed customer's content is a support incident. |
| Refund window | **7 days, once per rolling 12 months** | With the digital-content withdrawal-rights wording spelled out in the policy. |
| Referral reward | **1 free month to the referrer, on the friend's first paid invoice** | Credit accrues from `max(existing, now)`. |
| Referral stacking cap | **Cap it** (e.g. 12 months per referrer per year) | Commonly left uncapped — see §6. |
| Provider column naming | **Provider-neutral (`sub_*`)** | A vendor-named prefix leaks the vendor into the entitlement layer and out to client JSON, and the rename is free only while the columns are empty. |

## 6. Gaps and design briefs

Each is a **design brief only — no worked example ships with this file.** Record a pointer in the
optional `local/pointers/` overlay if you build one.

**G0 — The mock-completion guard's second condition.** §2.4 asks for "not production AND the database is not
production's"; the common implementation checks only the environment flag and relies on the environment split. Build:
resolve the opened schema name (`SELECT DATABASE()`) at boot, compare it with a committed production-schema name (the
same value `env.environments` uses for its `APP_ENV`↔`DB_NAME` check), and refuse mock completion — and every other
non-production-only write path — when they match, regardless of `APP_ENV`. Test it by pointing a staging config at a
schema named like production's and asserting the 403.

**G1 — Referral clawback on refund or chargeback.** A reward granted at the friend's first paid invoice and never
revisited leaves the referrer permanently credited when that friend refunds inside the window. Build: on a refund or
chargeback event for an account with a `qualified` referral inside the clawback window, reverse the credit (subtract the
granted days, floored at "now") and set the referral to a terminal `clawed_back` status. The handler is another
idempotent step in the inbox's `process`, so it inherits the CAS, the lock and the retry.

**G2 — Referral anti-abuse beyond self-referral.** Usually present: self-referral refusal and a `UNIQUE` referee.
Usually missing: a check that the two accounts do not share a payment instrument (compare the provider's
customer/payment-method fingerprint at the first paid invoice, refusing the grant on a match); a cap on stacked free
months per referrer per rolling period; and an attribution expiry so a `?ref=` captured a year ago cannot still pay out.
All three are cheap at grant time and expensive to retrofit after abuse.

**G3 — A billing reconciliation job.** Few implementations ever ask the provider "what do you think this customer's state
is?". Build a read-only periodic job that pages the provider's subscription list and compares status, plan and period end
against the local mirror, reporting differences to the admin overview without writing. It is the only thing catching a
permanently dead-lettered event, a silently misconfigured webhook endpoint, or a dashboard edit.

**G4 — Invoices and receipts on our surface.** Delegating entirely to the provider's portal is the usual choice. If a
project needs invoices in-app (B2B buyers usually do): store only the provider's invoice ids and totals from the webhook,
and render a list whose links mint a fresh provider-hosted document on click. Never re-render the tax document yourself.

**G5 — Proration and plan changes.** Refusing a second checkout and pointing at the portal is a legitimate
simplification, and the usual starting state. A project needing in-app upgrade/downgrade must decide who computes
proration (the provider, always) and how the mirror reconciles the resulting burst of events, which is where the ordering
rules in §2.4 stop being theoretical.

**G6 — Dunning visibility.** The provider dunns failed payments and emails the customer; few products surface "your
payment failed" in-app. Build: read the grace status from the mirror, show a persistent banner linking to the portal that
disappears the moment a successful payment event lands. Route through `notifications.md`.

## 7. Manifest rows

| Capability id | Tier | Done means |
|---|---|---|
| `billing.provider` | 3 | One provider behind a five-method interface with no SDK, selected by a pure function of configuration, failing closed with 503 in production and to a keyless mock outside it; sandbox by default; sandbox keys on local and staging, live keys only in production. |
| `billing.plans` | 3 | A `plans` table where code and duration are identity, one reader shared by the API, the server-rendered pricing page and the admin editor, derived per-month/saving figures, a coded fallback, and unconfigured durations hidden rather than half-sold. |
| `billing.webhooks` | 3 | Bounded read → signature verified over those exact bytes → durable insert keyed on the provider event id → 200; a five-state retry machine with a dead letter and admin visibility; account-scoped ordering plus a current-plan check under a per-account lock; payload minimised at ingestion. |
| `billing.entitlements` | 3 | Server-enforced at every paid write, resolved from the subscription mirror plus manual grants whose expiry the webhook always clears, one shared "paid right now" predicate, payer resolved per resource where teams exist, and a downgrade that refuses new work without deleting anything. |
| `billing.referrals` | 3 | Unambiguous codes, once-only server-side attribution with self-referral refusal, the reward granted on the friend's first paid invoice by a compare-and-swap whose result is checked and which reports retryable failure distinctly, with clawback and a stacking cap. |
