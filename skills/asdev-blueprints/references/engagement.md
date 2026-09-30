# Engagement — platform contract
*Part of the `asdev-blueprints` skill. `search.core` is Tier 2 where there is content to search;
`game.xp-levels`, `game.achievements`, `game.streaks` are Tier 3. Read this before scaffolding,
auditing, or building any of: search.core, game.xp-levels, game.achievements, game.streaks.*

## 1. Scope and timing

`search.core` is Tier 2 — before public launch — but only for a project that has a content corpus
worth searching (a dictionary, a catalog, a knowledge base, a page/post library). A project with
nothing browsable beyond a handful of static pages has no `search.core` need at all; record that as
`n/a (no searchable corpus)` in the manifest rather than building a search box for three pages.

Gamification (`game.*`) is Tier 3, "where applicable," and applicability is a real question, not a
formality: it fits a project with a **repeated user activity worth reinforcing** — daily study,
regular check-ins, recurring tasks where a visible sense of progress plausibly changes behaviour. It
does not fit a project whose core loop is a one-shot transaction (a demo viewed once, a ticket
resolved once) — bolting XP onto that kind of product adds surface area for no behavioural upside.
Decide applicability before building any of the three `game.*` ids; they are a matched set (a level
without any streak/achievement layer is unusual, but a streak or an achievement system genuinely can
exist without the others) so build only the pieces the project's actual loop calls for.

## 2. The contract

**search.core.** Data: none required beyond the content that already exists; optionally a computed
index (a MySQL `FULLTEXT` index, or a normalized/lowercased column a `LIKE` query targets) over the
column(s) actually searched. Surfaces: a query endpoint taking free text and returning ranked or
simply relevance-ordered matches; for an admin/internal search, a permission-scoped multi-entity
variant that returns grouped results across several tables in one request. Behaviour: the query is
scoped to what the caller is allowed to see — by ownership (`WHERE user_id = ?`) for a per-user
resource, by permission per entity group for an admin/global search — and that scoping is *inside* the
query the search runs, never a filter applied to results after the fact.

**game.xp-levels.** Data, in the general/minimal shape: an append-only events ledger row per
rewarded action (user, an event type, a canonical key identifying *which* occurrence of that type this
is, an XP delta, a timestamp) with a uniqueness constraint over `(user, event_type, event_key)`; a
level is a pure, stateless function of the user's lifetime XP total — never a separately stored,
separately maintained value. Surfaces: a function that computes level/progress from a total; a
read endpoint exposing the current level, progress toward the next one, and (for a UI progress bar)
how much XP the current and next level span. Behaviour: XP is granted by a server-observed event, never
accepted as a client-asserted fact; a level is *derived*, recomputed on every read, so adding a new
level tier or changing the curve needs no data migration and no per-user backfill.

**game.achievements.** Data: for a **threshold** achievement (reach level 10, earn 500 lifetime XP) —
none beyond the stat it thresholds against; it is a pure function exactly like the level itself. For
an **event-triggered** achievement (pass this specific exam, complete this specific one-time task) —
an award row keyed uniquely by `(user, achievement_key)`, because there is no monotonic counter to
re-derive the award from later. Surfaces: a read endpoint returning the full badge set (earned and
not-yet-earned, each with progress where meaningful) for a trophy-case UI. Behaviour: an award is
idempotent — evaluating the same event twice, including under a race, produces exactly one award, and
the mechanism that guarantees this is a database constraint, never an application-level
check-then-insert.

**game.streaks.** Data: a running streak count, the date of the last qualifying activity, and the
amount of "today's" progress toward the daily qualifying threshold; optionally a small number of
consumable "freezes" that can bridge one missed day without breaking the streak. Surfaces: a
read/recompute path invoked on the user's next activity (never a background cron that silently
resets streaks nobody was watching); if freezes exist, an endpoint to plan/cancel a freeze in advance.
Behaviour: the calendar comparison ("was yesterday the last active day, or was a day missed") runs
against the user's **own** day boundary — see `account.settings` for where the user's timezone is
recorded — not a single server-wide day boundary that quietly rolls over at the wrong local hour for
half the userbase; a freeze, if the feature exists, is consumed atomically under contention, never by
a read-then-write that a concurrent request can race.

## 3. Invariants

1. **Server-computed, never client-reported.** No endpoint accepts "the user did X, award Y XP" as a
   submitted fact — the server observes the action that earns the reward (a graded answer, a
   completed step, a login) and computes the reward itself. A client that could self-report XP could
   self-award it.

2. **Idempotent awards are a database constraint, not an application check.** One reference
   implementation's rewards ledger enforces a unique key over `(user_id, surface, event_key)`, so
   two concurrent requests racing the same reward both attempt an `INSERT`, exactly one commits, and
   the loser's unique-constraint violation is caught and turned into "re-read the winner's row" rather
   than a second reward. A `SELECT` to check "has this already been awarded" followed by a separate
   `INSERT` has a race window between the two statements; the constraint has none.

3. **A ledger is the source of truth for uniqueness; a denormalized counter (a `users.xp_total`
   column) is a legitimate read-optimization cache of it, but only of it — the ledger, not the
   counter, is what an idempotency guarantee is enforced against.** This distinction matters because
   it is easy to build only the counter and skip the ledger, and the result *looks* identical until the
   first race or replay. One reference implementation's base XP/streak path actually mutates the
   counter directly under a locked read (a row-lock-based concurrency guard, not a ledger-uniqueness
   one), with the ledger layered on top only as an *additional* anti-replay guard for a specific
   subset of events — not as the general architecture every XP grant in the codebase goes through.
   That two-tier shape grew historically rather than by design. A project starting
   fresh should put the ledger underneath *every* rewarded event from day one (§6), rather than
   reproducing it.

4. **A threshold badge is a pure function; an event-triggered badge needs a persisted, idempotent
   award.** One reference implementation's rank/XP-milestone badge function takes a lifetime
   total and returns the whole badge set with no table to keep in sync — adding a new tier is a code
   change, not a migration or a backfill. Its exam badges are the contrasting case: earning one is tied
   to a specific, non-repeating event (passing a specific exam), so it is read from the graded-attempt
   record itself rather than derived from any running total, and deliberately stays earned even if the
   underlying exam is later unpublished — an achievement, once earned, does not un-earn itself because
   its source content changed shape.

5. **A day-level calendar comparison is a coarser tool than a token-expiry comparison, and can
   reasonably use the server's own wall clock even where `foundation.md`'s "one clock" rule would
   otherwise insist on the database's.** An expiry measured in minutes (a password reset, an MFA
   challenge) is corrupted by even a small clock skew; a streak's day boundary is not — a one- or
   two-hour disagreement between PHP's and the database's clock essentially never flips which calendar
   date `date('Y-m-d')` returns. The two touchpoints of one feature — the write path and the
   read/comparison path — still need to agree on a *single* clock source, though: a streak-check
   function comparing against the application's own `date()`/`strtotime()` while the row it reads was
   written with the database's `CURDATE()` is harmless at day granularity in isolation, but it is
   still two halves of one feature on different clocks, and porting the pattern should collapse to
   one. Self-consistent day-scale use is a deliberate, scale-appropriate exception to the general
   rule, not a license to mix clocks carelessly — but if a project's day
   boundary is ever load-bearing for something security- or payment-relevant (not just "did the
   streak survive"), fall back to the stricter database-clock rule for that specific comparison.

6. **A consumable, contended resource (a streak freeze) is spent with a compare-and-swap, verified by
   the write's own row count — never by a read-then-decide.** One reference implementation's
   freeze-consumption function
   runs `UPDATE users SET streak_freezes = streak_freezes - ? WHERE id = ? AND streak_freezes >= ?` and
   trusts only the write's own affected-row count to decide whether the freeze was actually spent; an earlier version
   of the same idea that returned "success" unconditionally let two concurrent requests each believe
   they had spent the same freeze while genuinely consuming only one, silently doubling the effective
   freeze budget under contention.

7. **A billing-coupled engagement perk is gated at both the award site and the spend site,
   independently — never assumed present from one check alone.** One reference implementation's
   streak-freeze cap and planned-freeze eligibility are both re-derived from the
   user's *current* Pro status at award time and again at consume time, rather than trusting a value
   cached from an earlier check — a mid-session downgrade must not let an already-open freeze-planning
   form spend Pro-only inventory.

8. **A search endpoint over per-user content scopes ownership inside the query itself.** No reference
   project has a content search feature that is also per-user, but the invariant generalizes directly from
   an ownership rule used elsewhere in the same codebases (`AND user_id = ?` on every owner-scoped query, never a filter
   applied after the fact) — the same discipline applies the moment a search feature spans rows more
   than one account can own.

9. **`LIKE` with a leading wildcard is not free, and the decision to escalate past it should be a
   measured one, not a guess.** One reference implementation's content search runs bounded `LIKE LOWER(CONCAT('%
   ', ?))` queries and documents the actual measured cost of the leading wildcard against its table
   size directly in the code — cite the measurement, not an assumption,
   before deciding a project's table is big enough to need a real full-text index.

10. **An admin/global search scopes each entity group by its own permission check, so a
    lower-privileged caller gets narrower results, never an error.** One reference implementation's
    admin search checks a separate capability per entity group
    independently before even querying it — a moderator with only page access sees page
    results and nothing else, silently, rather than the endpoint refusing the whole request because
    one group was out of reach.

## 4. Reference implementations

*Pointers into the author's own repositories live in the optional `local/pointers/<name>.md` overlay,
which is not shared. The contract in §2 and the invariants in §3 stand on their own: they say what to
build and why, not where one team's copy happens to sit.*

## 5. Decision points

1. **`LIKE` vs. a `FULLTEXT` index vs. a dedicated search table/service.** Default: `LIKE` (ideally
   against a normalized column, anchored where possible to avoid a leading wildcard) for a small-to-
   medium corpus with prefix- or substring-shaped queries. Escalate to a native `FULLTEXT` index only
   once the `LIKE` cost is actually measured against the real table size and shown to matter — do not
   pre-optimize past the pattern more than one existing content-heavy reference project already
   ships with in production.
2. **Ownership scoping for search.** Default: scope in-query by owner for any per-user searchable
   resource (Invariant 8); scope in-query by permission per entity group for an admin/global search
   (Invariant 10). Never build a search feature that filters results after fetching them.
3. **Achievement persistence shape.** Default: a pure function of an already-tracked stat for anything
   that is a monotonic threshold (a level, a lifetime total); a persisted, uniquely-keyed award row
   only for anything tied to a specific, non-repeating event with no running total to derive it from.
4. **Whether streaks/gamification are billing-coupled at all.** This is entirely a per-project product
   decision, not a platform default. A project with no billing capability should ship streaks (and any
   freeze allowance) either uncapped or omitted entirely, rather than hardcoding a Pro-tier check
   against a billing table the project doesn't have.
5. **Whether gamification exists at all.** Apply the applicability test in §1 before defaulting to
   "yes" — record `n/a (no repeated-activity core loop)` in the manifest for a project it genuinely
   doesn't fit, the same way an `n/a` for any other capability needs a stated reason.

## 6. Gaps and design briefs

**No reference implementation yet — a general-purpose, non-domain-coupled rewards ledger.** The
minimal generic contract described in §2 — one append-only events table
(`user_id, event_type, event_key, xp_delta, created_at`, `UNIQUE(user_id, event_type, event_key)`)
underneath *every* XP-granting action, with `xp_total` as a read-cache derived from it rather than the
primary mutated value — ships no direct worked example here.
The near miss is the shape you are most likely to build by accident, so it is worth naming: a base
XP/streak path that is a locked-counter update, with a ledger existing only as an additional guard
layered on top of a few specific grading events, not as the architecture every rewarded action in
the codebase goes through. A project that builds the general form from day one — the ledger as the
*only* place XP is recorded, with `xp_total` as a materialized/cached sum kept in sync by the same
write that inserts the ledger row — becomes the reference for this shape. The individual mechanisms
that *do* have working references and should be reused directly are described in §3 above:
idempotent-award constraints (Invariant 2), pure-function level/threshold derivation (Invariant 4), and
compare-and-swap consumption of a limited resource (Invariant 6).

## 7. Manifest rows

| id | tier | done means |
|---|---|---|
| `search.core` | 2 | a query endpoint over the project's content corpus, scoped by ownership or permission inside the query itself — `n/a` recorded explicitly when there is no searchable corpus |
| `game.xp-levels` | 3 | XP is granted only from a server-observed event; level/progress is a pure function of the lifetime total, recomputed on read, never a separately stored value |
| `game.achievements` | 3 | every award is idempotent — a threshold badge as a pure function of a tracked stat, an event-triggered badge as a uniquely-keyed award row |
| `game.streaks` | 3 | a daily-activity calendar compared against the user's own day boundary, with any freeze mechanism consumed by compare-and-swap under contention |
