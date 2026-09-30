# Notifications — platform contract
*Part of the `asdev-blueprints` skill. Tier 1. Read this before scaffolding, auditing, or building
any of: notify.user, notify.admin, notify.email.*

## 1. Scope and timing

Tier 1: before the first real user. The moment an account can receive a reply, a reward, or a status
change it didn't cause in the same request (a support reply written by staff, a referral paying out
after the referred friend acts, a background job finishing), the user needs a way to find out that
isn't "happen to be looking at the right page." Admins need the mirror image the moment a background
process can fail or need a human — a machine-review queue filling up, a webhook dead-lettering, a
maintenance task going overdue — because nobody polls a dashboard for that on their own.

This capability is deliberately small in scope: it is a persistence seam and an inbox UI, not a
notification *platform* with channels, preferences, and digesting. Build the bigger version only when
a project's actual usage demands it.

## 2. The contract

**Data.** One table holding both user-facing and admin-facing notifications — a single audience
model, not two systems. Columns, in concept: recipient (a user id), a `kind` (a short, validated
machine identifier — `support_reply`, `referral_reward`, `billing_dead_letter` — never free text),
title, body, an optional in-app link, a count (for coalesced/repeated events), created-at, read-at
(nullable — unread is a null, not a boolean column, so "when was it read" is answerable without a
second query). A kind that must only ever reach an administrator is declared in a small allowlist
constant, not inferred from who happens to call the emitter.

**Surfaces.** An emission function (or two: one for a single recipient, one that fans out to "every
current admin"); a read API — unread count, and a bounded list, both scoped to the caller's own id;
a mark-read action (single row and mark-all); a retention/pruning sweep. On the client: a badge
showing the unread count, a lazily-loaded panel or page listing the notifications, and a mark-read
interaction that fires on open or on explicit dismissal. If an email channel exists, it is an optional
side effect of the same emission call, never a second notification system with its own audience logic.

**Behaviour.** Emission is best-effort: a missing table, a lock timeout, or any storage error must
never roll back — or even be visible to — the domain action that triggered it. A support reply must
land whether or not the notification insert succeeds. Reads and explicit mark-read actions are
ordinary, throwing domain calls, because their own controller can and should report a real failure —
best-effort is a property of the *emitter*, not of the whole feature. Repeated events of the same kind
to the same recipient about the same thing (a queue that keeps filling up) coalesce into one row with
an incrementing count, rather than flooding the inbox with duplicates. The "who is currently an admin"
predicate is re-checked at the moment of every privileged write, not only when the notification was
first considered — a demotion, lock, or deletion between the check and the write must win.

## 3. Invariants

1. **Emitters are best-effort and never roll back the domain write that triggered them.** This is the
   single organizing rule of the whole capability: a support reply, a referral reward, or a billing
   state transition is the thing that actually matters, and a failure to *also* tell someone about it
   must never turn into a failure to do it. One reference implementation's emission functions wrap
   every database interaction in a catch that returns a `['ok' => false, ...]` shape rather than
   throwing, specifically so a caller mid-transaction never has to decide whether a notification
   failure is worth rolling back real work over.

2. **Reads and mark-read stay ordinary throwing calls.** The best-effort rule applies to *emission*
   only. The unread-count and mark-read functions throw on a real storage failure, because their
   caller is a dedicated notifications endpoint whose whole job is to report that state accurately —
   swallowing a genuine failure there would just hide a broken feature instead of protecting an
   unrelated one.

3. **Admin-only kinds are re-checked inside the write statement, not only before it.** A fast
   eligibility check before opening a transaction is a UX nicety, not a security boundary — the
   boundary is the predicate repeated inside the `UPDATE`/`INSERT ... SELECT` itself, so a role
   demotion, account lock, or deletion racing the emission always wins atomically. One reference
   implementation does the cheap precheck for a fast refusal, then repeats the same active-admin
   predicate inside both the coalescing `UPDATE` and the `INSERT ... SELECT` — a check-then-write
   sequence here would have a window where a just-demoted account can still receive (or worse, still
   coalesce into) a privileged notification.

4. **Unread is a nullable timestamp, not a boolean.** `read_at IS NULL` answers "is it unread" and
   `read_at` itself answers "when was it read," from one column — a separate boolean would need its
   own timestamp column the moment anyone asks when something was read, which the retention sweep
   (Invariant 6) needs on day one anyway.

5. **A coalesced retry keeps only the failed subset, never a blind "send to everyone again."** One
   reference implementation's admin-broadcast function returns the failed recipient list from a
   delivery pass, and a caller that retries passes exactly that list back in rather than re-running
   the full admin audience — otherwise a partially-successful broadcast followed by a naive retry
   double-delivers to every admin who *did* receive it the first time, and a coalescing kind would
   double-count on top of that.

6. **Retention is two-speed: unread notifications live longer than read ones.** An unread notification
   is still-relevant information nobody has seen yet; a read one is a receipt. One reference
   implementation prunes read rows after 90 days and unread rows after 180, in small bounded batches
   (`DELETE ... LIMIT`, or the `SELECT id ... LIMIT` + `DELETE ... WHERE id IN (...)` shape on engines
   without `LIMIT` on `DELETE`), never as one unbounded sweep.

7. **The notification-store probe is a real query, run every time, not a cached boolean.** A
   migration for the notifications table can land in the same release as code that starts calling the
   emitter, and the two do not necessarily reach a given environment atomically. One reference
   implementation's readiness check runs a real `SELECT ... WHERE 1 = 0` and interprets the specific
   "table doesn't exist" error code per driver, rather than trusting a version flag or a cached
   assumption — every emitter and reader checks it fresh, so a pre-migration deploy degrades to "no
   notifications" instead of a fatal error on every request that touches the domain action.

8. **Any new account-owned table this capability's emitters can reach must join the same
   privacy-erasure and export coverage as every other user table.** A notification can carry a
   support-ticket subject line or a referral partner's identity — exactly the kind of thing an account
   export or deletion sweep is supposed to catch. Treat a new notification `kind` the same as any other
   new user-owned data: route it through `privacy-legal.md`'s export/erasure inventory rather than
   assuming it's exempt because it "is just a notification."

## 4. Reference implementations

*Pointers into the author's own repositories live in the optional `local/pointers/<name>.md` overlay,
which is not shared. The contract in §2 and the invariants in §3 stand on their own: they say what to
build and why, not where one team's copy happens to sit.*

## 5. Decision points

1. **One table for both audiences, or two.** Default: one — a `user_id` recipient column with an
   admin-only kind allowlist is simpler than two parallel read/mark-read/retention implementations,
   and the UI can filter on `kind` if an admin ever needs a dedicated view.
2. **Coalescing.** Default: on, per `(recipient, kind, link)` while unread, for any kind that can
   plausibly fire more than once about the same underlying thing before it's read (a review queue
   filling further, a repeated ticket reply). Off for anything that is inherently one-shot (a referral
   reward, a specific ticket's reply) — coalescing those would compress genuinely distinct events into
   a misleading single line.
3. **Retention windows.** Default: a 90-days-read / 180-days-unread split as a starting point; tune
   per project based on how actionable an old unread notification actually still is.
4. **Optional email channel.** See `notify.email` below — default off until a project has an actual
   need for out-of-band delivery, because every email channel added is a consent/quota surface that
   has to be maintained (see §6).

## 6. Gaps and design briefs — notify.email

**Design brief only — no worked example ships with this file.** The common state is that nothing sends
a notification-triggered email as part of the seam itself: where email exists at all, it is a separate,
direct call from the domain code — ticket-reply mail is the usual case — not routed through anything
resembling a shared emission function.

The shape, if a project needs it: treat the email send as an optional side effect *inside* the same
emission call, gated by three independent conditions, all of which must hold — (a) the notification's
`kind` is on a small allowlist of kinds worth an email (most in-app notifications are not urgent
enough to also justify an email); (b) the recipient has not opted out of email for that kind or
globally (a `notification_email_opt_out` style column or table — this is exactly the consent surface
`privacy-legal.md` governs, so route the toggle and its default through that file's consent model
rather than inventing a second one); (c) the project's `mail.transport` capability (`foundation.md`)
reports mail as actually configured. The send itself goes through `mail.transport`'s one `send()`
function like every other outbound mail, is best-effort exactly like the in-app emission (a failed
email must never fail the notification, which must never fail the domain write), and is rate-limited
or batched per recipient so a burst of coalescing in-app events doesn't become a burst of emails —
coalescing (Invariant 5-adjacent) should suppress the email side effect the same way it suppresses a
second in-app row. Do not build a second notification system for email; it is a delivery channel on
the existing seam, not a parallel feature.

## 7. Manifest rows

| id | tier | done means |
|---|---|---|
| `notify.user` | 1 | a signed-in user can see and clear unread notifications about events staff or the system triggered on their behalf, with emission that never rolls back the domain write it reports |
| `notify.admin` | 1 | the same persistence seam, addressed to a re-checked current-admin audience, covering at minimum a failure/attention condition a background process can reach on its own |
| `notify.email` | 1 | an optional, opt-in, best-effort email side effect on a small allowlist of kinds, routed through `mail.transport` and `privacy-legal.md`'s consent model — design brief only (see §6) |
