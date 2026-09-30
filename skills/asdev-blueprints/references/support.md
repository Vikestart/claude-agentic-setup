# Support — platform contract
*Part of the `asdev-blueprints` skill. Tier 2 (support.public, support.user, support.admin,
support.attachments), plus support.email as a Tier-3 design brief. Read this before scaffolding,
auditing, or building any of: support.public, support.user, support.admin, support.attachments,
support.email.*

## Contents
1. Scope and timing
2. The contract
3. Invariants
4. Reference implementations
5. Decision points
6. Gaps and design briefs — support.email
7. Manifest rows

## 1. Scope and timing

Tier 2: before public launch. A support channel that only works for a logged-in user leaves every
anonymous visitor — a lead who hit an error before registering, someone asking a billing question
before they'll commit to an account — with no route but a generic `mailto:`, which is invisible to
the admin queue and gives the visitor no way to check back on the answer. `support.attachments` ships
alongside the ticket flow itself, not later, because "how do I show you the error" is one of the first
things a real user asks. `support.email` is Tier 3 (where applicable): a project doesn't need an admin
mailbox until it actually has a `support@` address collecting real mail outside the ticket system —
most projects can go a long time on the ticket portal alone.

## 2. The contract

**support.public.** Data: a staging table for an unverified guest submission (name, email, subject,
body, a hashed verification token, an expiry) — kept separate from real tickets so an unverified
submission is structurally incapable of reaching staff. Surfaces: a public, unauthenticated submission
endpoint; a verification link/endpoint that promotes a staged submission into a real ticket; a way for
the now-verified guest to return to that one thread later. Behaviour: captcha and per-IP/per-email rate
limits apply before anything is staged; the submission is verified by a one-time emailed link *before*
it becomes visible to staff; the guest's later proof of ownership is a signed token, never a password
and never a bare identifier a stranger could guess or supply.

**support.user.** Data: a ticket (owner, subject, category, status, priority, timestamps) and a thread
of messages/events on it (author, role, kind — message vs. a system-generated status/assignment
event). Surfaces: create, list-own, reply, and — for the owner — close. Behaviour: the thread *is* the
history: every state transition writes a row into the same ordered thread the messages live in, rather
than a separate audit table nobody reads next to the conversation; quotas (open-ticket cap, tickets/day,
messages/hour, a cooldown between new tickets) are read-only pre-checks the UI can show verbatim, and
they vary by an explicit account tier, not just by whether an account exists at all (see `support.public`
— a guest is a third tier, not "logged-out free").

**support.admin.** Data: the same ticket/thread tables, plus assignment (to a staff member) and
priority. Surfaces: a filtered/sorted queue (open-and-needs-reply first), assign, reply, change
status/priority/category, and — a staff-only action — delete. Behaviour: staff replies and status
changes are not subject to the user-side quotas; a closed ticket stays closed to further customer
replies but a staff reply is still possible and reopens it; the admin queue and the customer-facing
list must read from the *same* settings/limits reader so the two surfaces cannot silently disagree
about what "Free" or "Pro" means (see Invariant 12).

**support.attachments.** Data: one row per uploaded file (owning message, original filename, an
opaque stored name, MIME, size). Surfaces: upload (as part of creating a ticket or a reply — the only
multipart-form path in an otherwise-JSON API), and a single auth-scoped download/serve endpoint.
Behaviour: files live outside the web root under a random opaque name, never at a guessable or public
URL; every upload is validated by an extension allowlist *and* a content sniff before it touches disk;
the whole batch in one request is validated before any file in it is written, so a bad file can't leave
earlier ones half-stored; the on-disk file is unlinked at every place the owning row would otherwise
become orphaned (message delete, ticket delete, account delete/anonymize).

## 3. Invariants

1. **A guest's later access to their own ticket is a signed token, never a password and never a bare
   identifier a stranger could reuse.** One reference implementation mints a guest access token as an
   HMAC over the ticket's reference code and a per-ticket random nonce — delivered once, moved into
   session storage client-side, and sent only in POST bodies afterward, never as a persistent URL
   query parameter that would end up in browser history, a referrer header, or a shared screenshot.

2. **A guest submission is verified before staff ever sees it, structurally, not just by convention.**
   One reference implementation stages every public submission in a separate guest-requests table, and
   only a verification function — triggered by the emailed one-time link — promotes it into a real
   ticket row. An unverified request cannot appear in the admin queue because the query the admin
   queue runs never reads the staging table at all; there is no flag to forget to check.

3. **Attachments live outside the web root and are served only through an auth-scoped endpoint —
   never a direct or predictable URL.** One reference implementation's serving function requires the
   caller to already have proven ticket ownership (or admin) before it is invoked at all, streams with
   `X-Content-Type-Options: nosniff`, and forces `Content-Disposition: attachment` for every type it
   cannot positively confirm is safe to render inline.

4. **Upload validation is two independent gates, and either alone is insufficient.** An extension
   allowlist alone doesn't stop a file whose *content* doesn't match its claimed type; a content sniff
   alone can't validate a container format (zip, docx, xlsx) that has no single canonical signature to
   inspect. More than one reference implementation requires the extension to be on an allowlist *and*,
   for every inspectable type, a `finfo` MIME sniff of the actual bytes to match — a `.png` that sniffs
   as anything else never lands, regardless of what its filename claims.

5. **A format that cannot be content-inspected is accepted on name and size alone, but is never
   rendered inline.** One reference implementation's viewability check allows only raster images, PDF,
   and plain text to open in a tab; a zip, a Word document, a spreadsheet — none of which can be
   sniffed — always downloads with `nosniff` set, so the browser is never given the chance to guess
   what to do with content nobody has verified.

6. **A multi-file batch is validated in full before a single file is written to disk.** One reference
   implementation's save function runs two passes: the first rejects the whole request if *any* file
   fails validation, the second moves and records files one at a time, and if any move or insert
   throws mid-pass, everything the pass already moved is unlinked before the exception propagates —
   so a ticket message with attachments is never left half-saved (some files on disk with no row, or
   rows with no file).

7. **Account deletion anonymizes a ticket's thread, it does not simply cascade-delete it.** Thread
   *text* is retained (it may be needed for a billing dispute or an abuse claim), while attachments —
   the PII-richest part and not needed for that defense — are deleted. One reference implementation's
   anonymization function runs inside the same transaction as the rest of account deletion, using the
   same legal-hold pseudonym every other retained table uses so a dispute can still correlate rows
   without any of them naming the person. Its strict mode throws (rolling back the whole deletion)
   rather than reporting a deletion that didn't actually happen, when it cannot even *queue* the file
   purge it is about to promise.

8. **File deletion from disk is queued, never unlinked synchronously inside an unrelated request.**
   One reference implementation enqueues attachment purges rather than calling `unlink()` inline
   during account deletion — a failed unlink is then a retryable row in a queue, not a silent orphan
   nobody notices until a disk audit years later.

9. **Quota context is explicit and at least three-way once a public surface exists — free, pro, and
   guest/public are not the same risk profile.** One reference implementation's context set gives the
   anonymous public surface its own (tighter) limits rather than inheriting the free-tier account
   limits, because an anonymous submitter costs nothing to generate and is a materially different
   abuse surface than a registered free account.

10. **A third-party captcha/anti-abuse check fails open on a network error to the provider, and closed
    on an invalid or missing token.** These are different threats: a provider outage is an
    availability problem the whole site shouldn't inherit, while a missing or rejected token is exactly
    what the check exists to catch. One reference implementation's verification call returns success
    (logged) on an unreachable verification service, but refuses on a genuinely bad or absent token —
    server-side quotas remain the backstop while the third party is down.

11. **A closed ticket is read-only for the customer, but staff retain reply power, and a staff reply
    reopens it.** One reference implementation's reply handler refuses a customer's reply on a closed
    ticket while an admin's reply is still accepted — a customer cannot keep arguing into a resolved
    thread, but staff can always follow up, and doing so is itself the signal that the ticket is
    active again.

12. **The admin panel and the public-facing form must read a setting through one shared function, never
    parallel hardcoded key names.** One project shipped exactly this bug: the admin panel saved a
    captcha setting under one pair of key names while the public ticket flow read a differently-spelled
    pair for the same intended setting — so captcha silently never engaged despite looking fully
    configured in the admin UI. A settings reader both surfaces call, rather than each surface
    embedding its own key string, makes this class of bug impossible rather than merely unlikely.

13. **Any client-supplied redirect target on a guest-facing form is validated to a same-site,
    root-relative path before use.** One reference implementation's path validator strips control
    characters (killing CR/LF header-injection attempts) and refuses anything that isn't a plain
    `/path` — not `//host` and not `/\host` — because an unauthenticated form's `return_url` field is
    exactly the kind of value an attacker can set to build an open-redirect or phishing link, and a
    public support form is reachable by definition without an account.

## 4. Reference implementations

*Pointers into the author's own repositories live in the optional `local/pointers/<name>.md` overlay,
which is not shared. The contract in §2 and the invariants in §3 stand on their own: they say what to
build and why, not where one team's copy happens to sit.*

## 5. Decision points

1. **Guest identity proof.** Default: a signed, session-scoped token for any project handling anything
   beyond the most trivial contact form. A tracking-id-plus-email pair is acceptable only for a
   genuinely low-stakes public form with no sensitive thread content.
2. **Attachments outside the webroot: where.** Default: an env-configured directory, blank = feature
   disabled (never a guessed path) — the only real decision is the path itself, which is
   per-deployment configuration, not a design choice.
3. **Verification-before-queue for guest submissions.** Default: required, whenever the guest surface
   is reachable from the open internet without another bot mitigation strong enough to substitute.
   Skippable only alongside a captcha strong enough on its own and a tolerance for staff occasionally
   seeing spam.
4. **Quota granularity.** Default: three-tier (free / pro / public) the moment a public guest surface
   exists at all — a guest costs nothing to generate and is not the same risk as a registered free
   account. Two-tier (free/pro only) is fine for a project with no public/guest support surface.
5. **Canned replies and post-resolution ratings.** Default: build these only once the admin queue has
   enough real volume that staff efficiency is the bottleneck — they are a genuine but non-essential
   layer on top of the core create/reply/attach/resolve loop.

## 6. support.email — SHIPPED, two independent reference implementations

**This is no longer a brief.** More than one reference project has built this, and the decisions below
are the lived contract, not a proposal. Two independent builds — one in an action-dispatch idiom, one
in a REST-controller idiom — converged on the same shape: a dependency-free IMAP4rev1 + ESMTP/AUTH
client written in PHP over raw TLS sockets (not `ext-imap`, not a Composer package, and not a provider
webhook), with credentials stored encrypted in the database under an integrations key rather than in
`.env`, so the mailbox is configured from the admin panel rather than a deploy-time secret.

- **⚠️ FOLDERS MUST BE DISCOVERED, NOT NAMED — the single most important lesson in this file.**
  Both initial builds hardcoded the archive folder's name (one later made it configurable), and both
  failed on the real server, because a common IMAP-server-on-a-hosting-panel setup namespaces folders
  under a prefix like `INBOX.` — the archive folder turns out to be `INBOX.Archive`, `EXAMINE Archive`
  returns NO, and archiving fails every time with no hint why. Hardcoding the namespaced name only
  moves the guess to the next server, and letting an operator type the name only moves it to them.
  **Speak `LIST` and match RFC 6154 special-use flags** (`\Archive`, `\Sent`, `\Drafts`, `\Junk`,
  `\Trash`), which state a folder's purpose independently of its name and survive the namespace
  prefix, localisation and renaming; fall back to the last path segment; drop `\Noselect`. **Match the
  flags case-insensitively** — they are case-insensitive by grammar, and a strict comparison silently
  falls back to name-guessing, which is the original bug one layer up.
- **⚠️ Validate every fragment before writing anything to the socket.** A command builder that writes
  plain fragments to the socket *before* validating a literal's length can leave a truncated,
  unterminated command on the wire the moment an over-long mailbox name or search term is refused
  mid-write — the connection still reports itself usable, so the next command is read as the previous
  one's continuation. Validate every part in a pre-pass before writing anything, and poison the
  session if a fragment guard trips after the tag is already out, rather than trying to recover a
  partially-written command.
- **⚠️ Parse mailbox names and delimiters to the letter of the grammar, not by convenient regex.** A
  greedy name-tail pattern like `(.+)$` silently drops a literal-form mailbox name, because a
  literal's bytes can contain the CRLF a naive line reader splices on — so that folder simply never
  appears, which is the same quietly-missing-folder failure `LIST`-based discovery was adopted to end.
  And a delimiter taken as raw text rather than parsed as an IMAP nstring can pick up an extra byte on
  a backslash-separator server, silently breaking every path split downstream. Parse the mailbox name
  in all three IMAP astring forms and the delimiter as an nstring — never a hand-rolled regex over the
  raw line.
- **⚠️ Authenticating as the mailbox does not put a copy in the Sent folder.** It is tempting to assume
  it does, and easy to say so in a comment without checking. SMTP submission delivers to the
  recipient; populating a Sent folder is a separate IMAP `APPEND`, which a minimal client typically
  doesn't implement — so a sent reply may be retained nowhere. That is consistent with a
  store-nothing design, but it must be *stated*, not assumed as a side effect that isn't actually
  happening. Set `\Answered` on the original message after a successful send (it is already in the
  flag allowlist most servers accept) — without it, two admins working the same mailbox cannot tell a
  message was already answered and will answer it twice.
- **Prefer `Reply-To` over `From` when replying.** Mail from contact forms and system mailers arrives
  as a no-reply `From` address with the real correspondent in `Reply-To`; replying to `From` sends the
  answer into a no-reply void and the customer never hears back. Fetch `REPLY-TO` in the read path —
  it is easy to fetch it for the list view and then discard it before the reply path needs it.
- **What NOT to copy:** a single admin-action-dispatch surface and a one-controller-per-area split are
  each right for their own project's existing shape — join the admin surface the host project already
  has, and never create a second authorization boundary for this one feature.

**Before assuming this shape, measure the target host** rather than assuming it: whether the mail
server's IMAP and SMTP ports are actually reachable from the app server, whether PHP's `imap`
extension is loaded (if it is, that changes the calculus — a loaded extension may be the better
starting point instead of a hand-written socket client), and whether outbound TLS sockets and the
needed stream functions are actually permitted by the host's `disable_functions` policy. A host with
no realistic path to receive mail into the admin's own mailbox at all changes the calculus entirely —
confirm the shape is even possible before designing around it.

**The recommended shape:**

- **A mailbox VIEW, not ticket conversion — email stays email.** The alternative — inbound mail
  becoming a ticket, reusing the existing ticket pipeline's assignment/status/autoclose machinery — is
  worth recording as the cheaper fallback if a two-queue split (a Tickets queue and a separate Mailbox
  view) proves annoying in practice for a given project. Present both to the owner; default to the
  mailbox-view shape.
- **Read live, store nothing.** The admin panel talks to IMAP per request rather than persisting
  copied mail into the application's own database. This is the decision that keeps the whole feature
  small: storing someone else's email would pull in the full account-deletion erasure sweep, GDPR
  export coverage, a retention policy, and a privacy-policy update — none of which is needed if nothing
  is ever written down.
- **Read, reply, mark-read, archive. No delete.** Archive means moving the message to a folder on the
  mail server, so every action stays recoverable from any ordinary mail client — never destroy mail the
  admin panel is only borrowing a view of.
- **A sibling admin leaf beside the ticket queue**, not tabs inside the same container — matching
  `admin.md`'s reuse rule for how a new admin section joins the existing navigation.

**Security invariants — these are the contract, not optional hardening:**

- **HTML email is attacker-controlled markup rendered to an administrator's browser.** Anyone on the
  internet can send mail to a public support address, and rendering an HTML email is rendering
  arbitrary third-party markup inside the one session that can do everything. Prefer the `text/plain`
  part of a multipart message; for an HTML-only message, convert to text (strip tags, decode entities)
  rather than attempting to sanitize the HTML — a dependency-free HTML sanitizer that is actually safe
  is a project in itself, and the failure mode of getting it wrong is XSS against the admin panel. All
  rendering goes through the project's existing output escaper; never `innerHTML` with message content.
- **No remote content loads from a message** — no images, no CSS, no iframes — which is both a
  tracking-pixel leak and an SSRF-adjacent fetch initiated from the admin's own browser. The existing
  CSP already blocks most of this; the mail renderer must not defeat it with an inline exception.
- **IMAP command injection.** Folder names and search terms travel into raw IMAP protocol commands.
  Every caller-supplied string is sent as a length-prefixed literal (`{n}\r\n…`), never interpolated
  directly into a command line; test that a folder name containing a quote, a backslash, or a raw CRLF
  cannot break out of a command.
- **Credentials.** The mailbox password lives only in the project's git-ignored secrets file
  (following `env.secrets` — e.g. `SUPPORT_IMAP_HOST/PORT/USER/PASS`, `SUPPORT_SMTP_*`), is never
  logged, never returned by any action's response, and a failed login must never echo the mail
  server's raw response back to the caller verbatim.
- **No new authorization boundary.** This feature adds actions to the *existing* admin-gated endpoint
  rather than a new one — a second copy of an authorization boundary is exactly how one of the two
  copies ends up wrong. Every mutating action still goes through the project's existing admin
  gate + CSRF check.
- **The admin activity log records that a message was opened** (mailbox, message id, admin, timestamp)
  — reading a customer's email is itself a privacy-sensitive act worth an audit trail — but never the
  message's content.
- **The existing plain mail-sending helper cannot send these replies.** A basic `mail()`-based sender
  with a hardcoded `From:` and no authentication cannot send *as* `support@<domain>`, and cannot set
  `In-Reply-To`/`References` — without those headers a reply will not thread in the recipient's mail
  client at all. A reply needs SMTP `AUTH` from the actual mailbox account with proper threading
  headers, which is why this is its own small transport client rather than a `mail.transport` reuse.
- **Attachments are listed and downloadable, forced as `Content-Disposition: attachment` with
  `nosniff`** — the same posture as `support.attachments` — and if a safe download path is at all
  uncertain during review, ship list-only (name/size/type, no download) and let the admin open the
  message in a real mail client instead. This mirrors the "containers are accepted but never rendered
  inline" invariant above (Invariant 5), applied to a channel with no upload-time validation control at
  all.
- **Availability.** The mail server is now a dependency of exactly one admin leaf. Every failure path
  degrades to a clear "mailbox unavailable" state; it must never break the ticket queue sitting beside
  it, and must never break the Support section as a whole.
- **The live mailbox is never in the automated test battery.** It is an external dependency with a
  real credential — including it would make the release gate non-hermetic and flaky, and would risk a
  real credential reaching a test log or a subagent transcript. Tests run against a scripted fake
  socket (parsing, literal-encoding, injection refusal, truncation handling); live verification against
  a real test message is a manual staging step, recorded in the walkthrough, not a suite.

**Status:** shipped in two independent reference implementations, one per architectural idiom. Port
from whichever idiom matches the host project; either way, validate every fragment before writing
anything to the socket (see above).

## 7. Manifest rows

| id | tier | done means |
|---|---|---|
| `support.public` | 2 | an unauthenticated visitor can submit a request, gated by captcha and rate limits, verified before staff sees it, with a signed way to return to that one thread |
| `support.user` | 2 | a logged-in account can create/reply/close tickets under explicit per-tier quotas, with the thread itself as the state-change history |
| `support.admin` | 2 | staff can queue, assign, reply, and transition status/priority, reading the same settings the public/user surfaces read |
| `support.attachments` | 2 | uploads validated by extension allowlist + content sniff, stored outside the web root under opaque names, served only through an auth-scoped endpoint, unlinked at every relevant delete |
| `support.email` | 3 | an admin can read, reply to (with correct threading, from the real address), mark-read, and archive a support mailbox from the same panel, storing nothing and unable to delete |
