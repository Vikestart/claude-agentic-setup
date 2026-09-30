# Identity and accounts — platform contract

*Part of the `asdev-blueprints` skill. Tier 1 (`auth.sso` is Tier 3). Read this before scaffolding, auditing, or building any of: auth.core, auth.verify-email, auth.password-reset, auth.password-policy, auth.remember-me, auth.mfa, auth.captcha, auth.rate-limits, auth.sso, account.profile, account.management, account.settings.*

Related files: `admin.md` owns admin authority and the settings store; `privacy-legal.md` owns consent, export and deletion (this file only names the entry points); `foundation.md` owns `.env`, secret resolution, the mailer and the three environments; `notifications.md` owns the emitters that account events fire. Code style — session bootstrap, PDO options, escaping, endpoint shape — belongs to `asdev-conventions` (`references/php.md` §"Sessions, auth, secrets", `references/projects.md`). This file owns *which flows exist and what each must guarantee*, never the idiom.

## 1. Scope and timing

Everything a project needs so a stranger can become an account holder, prove they own it, keep it, and lose access to it on demand. Tier 1: it must exist **before the first real user**, because every one of these flows is retrofitted at a cost measured in incidents — three of the invariants below were paid for that way.

`auth.sso` is the exception. It ships no worked example here (§6), so it stays Tier 3 until a product need appears.

Nothing here is a domain feature. If a rule is about what the product *does* with an account, it belongs in that project's own `AGENTS.md`.

## 2. The contract

Architecture-agnostic. "Endpoint" means *a reachable operation* — a REST path+method, an `action` in a POST body, or an admin AJAX action — whichever the project already uses.

### Data (in concept, not column names)

- **Account** — identifier(s), password hash, role reference, status flags (`locked`/`suspended`), `email_verified`, a **revocation counter** (`session_epoch` / `session_version`), `created_at`, `last_login_at`, `last_login_ip`. Optionally `scheduled_deletion_date`, a login-address allowlist, an acquisition source.
- **Pending email change** — the requested address, a hashed single-use token, a sent-at stamp. Deliberately *not* the live address (invariant 14).
- **Email verification token** — hashed, expiring, one live slot per account.
- **Password reset token** — hashed, expiring (1 hour), single-use, superseding.
- **Persistent-login tokens** — one row per device: `user_id`, plaintext `selector`, `sha256(validator)`, absolute or rolling `expires_at`, `last_used_at`. Capped per user.
- **Second factor** — encrypted TOTP seed, `mfa_enabled_at`, the last accepted time step (replay guard), and hashed single-use recovery codes.
- **Attempt ledger** — one small append-only table serving every throttle (login, registration, reset mail, MFA guesses, and every password re-authentication prompt — export, deletion, change email, change password). Bucketed by an attacker-*uncontrolled* dimension; see invariant 12. ⚠️ The re-authentication prompts are the ones that get forgotten, because they sit behind a session and feel already protected: a prompt that verifies the password without recording the attempt hands a hijacked session an unlimited password oracle. Meter every one of them.

### Surfaces

| Flow | Operation | Auth state |
|---|---|---|
| Register | create account, issue verification | anonymous |
| Login | password → session, or a pending-MFA state | anonymous |
| MFA verify | promote a pending state to a session | half-authenticated |
| Logout | tear down session + this device's token | authenticated |
| Session probe | report signed-in state + boot config | either |
| Verify email | confirm a token (from a link, so a GET) | anonymous |
| Resend verification | re-issue, throttled | authenticated |
| Forgot / reset password | issue link; consume link | anonymous |
| Change password | re-auth, write, revoke everywhere | authenticated |
| Change email | re-auth, park, confirm from the NEW address | authenticated |
| MFA setup / confirm / disable / re-roll codes | re-auth each time | authenticated |
| Profile + settings read/write | preferences, consent | authenticated |
| Export / delete account | → `privacy-legal.md` | authenticated |

Pages: login, register, forgot-password, reset-password, verify-email, profile. Keep them plain partials with no session or header calls of their own.

### Behaviour rules

- **Registration** creates the account and issues a verification token. What an unverified user may do is a per-project choice (§5), but it is enforced server-side.
- **Login** verifies the password *first*, then every other refusal in turn (status, address allowlist, maintenance, verification, second factor). Every refusal after the password uses wording that does not reveal which condition failed. ⚠️ The status check is the one that drifts ahead of the password check, because an early exit reads like tidy code: "this account has been locked", answered *before* `password_verify`, in its own distinct wording and without recording the attempt, is an unthrottled lock-state and account-existence oracle for any identifier a stranger cares to try.
- **Session establishment** always rotates the session id and stamps the account's current revocation counter.
- **Every authenticated request** re-reads the account's authoritative row and compares the counter, the status and (where used) the calling address. A mismatch tears the session down and the request proceeds signed-out.
- **Every credential-consuming step** — reset token, email-change token, recovery code, MFA time step — is claimed by a single conditional write judged on affected rows, under the account row lock.
- **Every "this ends other sessions" action** — password change, password reset, email change, MFA enable/disable, admin lock, suspension — bumps the counter *and* deletes the account's persistent-login tokens, in the same transaction as the change that motivated it.

## 3. Invariants

Each rule is followed by the incident or reasoning that produced it.

1. **The client's notion of "signed in" is decoration; the server re-derives it from the database on every request.** Memoise one auth row per request and serve the epoch check, the status gate and the role read from it — one query, and then no temptation to skip it.

2. **Distinguish "the row is unreadable" from "the row is gone", and fail in opposite directions.** A DB blip must fail *open* (a transient outage must not mass-log-out every user); a missing user row must fail *closed* (a ghost id must not reach a controller). Two shapes both work: a `$missing` out-parameter carried beside the returned row, or a session-state reader that returns a distinct `unknown` state — so a missing column or a blip never locks everyone out of the product.

3. **A revocation counter on the account row, checked on every authenticated request, is what makes "locked" a state rather than a label.** The finding that produced it: login and remember-me re-auth already refused revoked accounts, so a *live session* was the single hole — lock a user and their open tab kept working until they chose to sign out.

4. **Revocation and the state change it accompanies are one transaction, and the result is checked.** Make it structural — one named "revoke live access" function — so an operator who sees "locked" is never looking at an account whose sessions still work. The other half is the return value: a password reset that discarded the revocation result still answered "you are signed in" after a failed token wipe, while old devices stayed valid. Roll the whole reset back instead.

5. **Verify the password before every other refusal.** A login-address allowlist is checked *after* the password verifies and *before* any session, token or MFA challenge exists — a correct password from a disallowed address produces nothing to carry away, and a wrong password is still refused first, so that check is not an account-existence oracle. Suspension is checked after `password_verify` for the same reason. Any refusal placed *ahead* of the password check — especially one that exits without the failed-attempt insert — turns the endpoint into an unthrottled oracle for whatever it refuses on.

6. **Email existence is never disclosed; username availability is.** Registering an already-registered address returns the *same* "check your email" response and mails the existing owner ("you already have an account — use Forgot password"), rate-limited to one such notice per address per hour so repeated probes get silence. Forgot-password always answers the same neutral 200 — including when it is throttled, or when the account is suspended and deliberately gets no link. A handle, by contrast, must be reportable as taken or the user cannot pick one.

7. **Tokens are hashed at rest; the plaintext exists only in the emailed link or the cookie.** Verification, reset, email-change and remember-me validators are all `sha256` in the database. A dump must not be replayable. Corollary: **never log a token.** Gate the convenience "here is the link" log line on being on the local dev box specifically — a mailer that logs the whole message, link included, on *any* non-production host leaves live reset links sitting in staging's `error_log`, which is survivable only for as long as staging is unreachable from the internet.

8. **ONE CLOCK. An expiry is written and read by the same clock — and unless there is a reason otherwise, that clock is the database's.** One project measured a two-hour gap on production (Plesk runs PHP in UTC, MariaDB follows server-local). Damage scales *inversely* with the TTL: 1-hour reset tokens and 10-minute pairing codes landed `expires_at` before `NOW()`, so **every reset link was expired at the instant it was created**, while the 24-hour verification token merely ran a 22-hour window — worse in one respect, because nothing reports it. The same class bites from the other side too: reading a `scheduled_deletion_date` with PHP's `strtotime` could **purge a user still inside their 14-day grace window on a routine sign-in**. ⚠️ This is structurally invisible on a dev box, where both clocks inherit one OS timezone and the skew is exactly zero. Do **not** "fix" a recurrence by setting `date.timezone` — that is configuration, and it drifts again on the next server.
   - Self-consistent PHP-clock use is fine and is not the bug: a pending-email window written *and* read with PHP's clock is a legitimate choice, and so is pinning both sides to UTC (`gmdate` + `UTC_TIMESTAMP()`). **Mixing** is the bug, and it hides in the least-watched windows — an admin lockout that writes `last_attempt = NOW()` and reads it back through `strtotime()` against `time()`, or an email-verification window written as `NOW()` and read as `strtotime() < time() - 48h`, which on a two-hour split is really 46 or 50 hours and nothing reports it. Grep for both halves of every window together, never one at a time.

9. **Consuming a single-use credential is a decision only one caller can win.** Make the comparison and the write the *same* conditional statement, judge it by affected rows, and hold the account row lock. Three separate incidents of this one shape: two requests carrying the same reset link both set a password and both signed in, and the loser held a session on an account whose password they did not choose; a select-then-update recovery code could be spent twice, and the last-accepted MFA step could be read by two pending sessions that both accepted the same code; and a backup-code array kept as a read-modify-write meant **one leaked backup code was worth as many logins as an attacker could fire in parallel**. ⚠️ That last shape is the one to grep for: decode a JSON array of codes, splice out the match, write the array back, no lock and no affected-rows check.

10. **A pending login grants nothing.** Park it under its own session key, never `user_id`, so every existing "require a user" check keeps refusing; only the verify step may promote it, and only through the same fixation-safe login a password login uses. That is the load-bearing rule of the whole MFA design. One step further is worth taking: the pending challenge also carries the `session_version` and role it was minted against, re-checked under the row lock, so a password reset, an admin lock or a role change inside the five-minute window **ends** the challenge instead of being stamped onto a full session. A challenge minted before that field existed carries 0, which matches no real account state — the fail-closed direction.

11. **A second-factor guess budget must be durable, and a correct password must not clear it.** The finding: the only budget was a per-session counter, and password success also deleted that IP+identifier's failed-login rows — so anyone holding the correct password could throw the cookie jar away, log in again, and buy five more guesses, forever. Six digits were a delay, not a rate boundary. The budget has to refuse *before* a challenge is even minted.

12. **The column that holds a throttle's namespace is a security boundary.** Put the bucket name in the `ip` column and the key in `identifier`, because `identifier` stores the *submitted* login name (attacker-controlled) under an accent- and case-insensitive collation — a string namespace there is forgeable by anyone who can POST a wrong password, which would hand a stranger a remote lockout of somebody else's second factor. Related: key the login throttle on **(ip, identifier)**, not either alone — IP-only locks out a whole NAT or campus, identifier-only lets an attacker lock a victim out from anywhere.

13. **The rate-limit decision itself must be atomic, and it fails closed.** The incident: `DELETE` → `SELECT COUNT` → `INSERT` as three autocommit statements let N parallel requests all read a count below the limit, and that one race weakened login throttling, MFA verification, password-reset, share unlock, public ingest, credential issue, support and the anonymous beacons *simultaneously*. Serialise on a named lock derived from the bucket (so different buckets never wait on each other) and **refuse** on lock timeout — waiting a full second on one bucket *is* the abuse signature. ⚠️ Advisory-lock names are **server**-scoped: namespace them by schema, or a staging worker blocks on production's, because both used the same literal name on one server.

14. **Changing the email address is verify-before-switch.** The stored address is both the login identifier and the password-recovery identifier, so a direct write from a hijacked session redirects account recovery to an inbox the attacker controls. Park the new address behind a single-use token, keep the live address pointing at the old inbox until the link comes back, step up with the current password (plus a second factor when enrolled, and a backup code used there is *spent*), warn the **old** address at request time — the only moment that warning is actionable — and again after the switch, and let the commit bump the counter and drop every remember-me token. ⚠️ The shape this replaces is common and easy to miss in review: a profile endpoint that writes the address column directly, with no re-authentication and no proof that the new inbox exists. That is a one-request account takeover from any stolen session.

15. **A TOTP seed must be encrypted at rest under a key held outside the database, and that key belongs to the *database*, not the environment.** A database restored or cloned elsewhere (production → staging for a rehearsal) must carry its key with it, or every enrolled user is locked out of the copy; say so in the `.env.example` — the key MUST be identical wherever the same users table is opened. A seed has to be recoverable to derive codes, so hashing is not an option; plaintext plus one dump is every user's second factor. Recovery codes *are* hashed and single-use. ⚠️ Two operational traps: the key must **match** wherever a database is restored or shared, or every stored secret becomes undecryptable and MFA users can only get back in with a recovery code; and losing it has the same effect, so it belongs in the restore checklist beside the database. Keep it separate from other at-rest keys — split an integrations key from the MFA key so a leaked webhook token is not a step toward everyone's second factor. ⚠️ Audit for the simplest failure first, because it is also the most common: a seed column stored in plaintext, with no replay guard at all.

16. **Every MFA management action re-authenticates.** MFA is the control that survives a stolen session, so turning it off must cost more than possession of a logged-in tab — require the password *and* a current code to disable. Enabling and disabling both revoke every device.

17. **After a revocation bump, the acting session must be re-established from a freshly read counter.** Worth documenting at both sites that hit it (changing a password, and the re-login that follows an MFA change): the memoised auth row was loaded *before* the bump, so letting login consult it stores the stale value and kills the very session that just changed the password, on its next request. Re-read the counter inside the locked closure and write it back to the session.

18. **Remember-me is a split token: plaintext selector for lookup, `sha256(validator)` for the secret, `hash_equals` to compare.** Never store or log a raw validator; cookie re-auth goes through the same fixation-safe login path. Two rotation designs are both legitimate and the choice is §5 — but **if the validator rotates, a grace window is mandatory**: one project chose not to rotate precisely because an SPA fires concurrent requests and per-request rotation caused race logouts; another rotates with a compare-and-swap plus a 30-second acceptance of the just-superseded validator. Under a rotating scheme, a live selector with a stale validator is **theft**: revoke every token for that user *and* bump the counter, or a session already minted from the stolen cookie survives the response to the theft.

19. **Remember-me deliberately skips the MFA challenge — and that is only safe because enabling/disabling MFA and password changes revoke every token.** Do not regress that revocation; it is a standing invariant, not an implementation detail.

20. **Captcha is per surface, inert unless fully configured, and fails open on anything that is not a definite visitor fault.** Two projects arrived here independently: a half-configured captcha is simply switched off, never a form that cannot submit; an unreachable provider, a bad secret or an unknown error code **allows** and logs; only "token missing / invalid / already used" blocks. The rate limits and tier caps are the real backstop, and a support channel or a login must never break because a third party is down. Login captcha only engages *above a failure threshold*, so normal sign-ins are never challenged.

21. **A rate limiter records a hit on every call, so meter after validation for user-authored content and before it for credential attempts.** A typo must not burn a daily slot — but on login and forgot-password the *attempt itself* is what is being limited, so those meter first. (One project states the rule outright; another's registration throttle records only after the field validations pass, for the same reason.)

22. **One password policy function, called at every write site.** One function, called from registration, reset, the profile change, admin password reset and account provisioning — five paths, one rule, so a weaker path cannot appear by accident. Include the **bcrypt 72-byte ceiling**: `PASSWORD_DEFAULT` silently ignores bytes past 72, so accepting a longer value makes visibly different passwords authenticate identically. Length is the control; composition rules are largely theatre (see §5).

23. **Booleans arriving from a client are read strictly.** The incident: `!empty("false")` is `true`, so a client that stringifies its booleans turned signups on, started the store selling, and switched on the admin-MFA requirement that then locked every admin without MFA out of the admin API. Accept real booleans, `1`/`0`, and the four strings; answer 400 on anything else rather than guessing.

## 4. Reference implementations

*Pointers into the author's own repositories live in the optional `local/pointers/<name>.md` overlay,
which is not shared. The contract in §2 and the invariants in §3 stand on their own: they say what to
build and why, not where one team's copy happens to sit.*

## 5. Decision points

| Decision | Options | Default |
|---|---|---|
| Public registration | open / invite / admin-provisioned only | open, behind an admin toggle that fails **open** on a DB error |
| What an unverified user may do | sign in but restricted / cannot sign in at all | sign in but restricted — a user who cannot get in cannot resend, and every gate stays server-side either way |
| Login identifier | email only / username **or** email | email only. The dual namespace needs cross-column conflict checks at every creation and change site, because a username matching another user's email makes login ambiguous — and a project that accepts both identifiers without such a check has that ambiguity live and will not notice |
| Password policy | length floor only / floor + character classes | length ≥ 12, no composition rules, 72-byte ceiling enforced. Classes are the weaker control and push users toward `Password1!` |
| Breach check | none / a k-anonymity range API | none by default. If added: k-anonymity range API, advisory only, **fail open** — never let a third party's outage block a password change |
| Remember-me rotation | rotating + absolute expiry / non-rotating + rolling window | rotating with a grace window, for the theft signal — unless the client fires concurrent requests and a grace window is impractical |
| Remember-me lifetime | 30 days in every implementation | 30 days, absolute |
| MFA availability | all users / admins only | all users; optionally *require* it for admins via a setting that gates only the admin surface, so it can never lock anyone out of the product itself (`admin.md`) |
| "Remember this device" for MFA | not implemented anywhere; the remember-me cookie is used as the trusted-device signal instead | inherit the remember-me approach — a second trusted-device store is a second thing to revoke and forget |
| Captcha provider | Cloudflare Turnstile / reCAPTCHA v3 | Turnstile — pass/fail, no score to threshold, privacy-first |
| Captcha surfaces | register, forgot-password, support, login-above-threshold | all four, each with its own toggle, all inert until keys exist |
| Login lockout | hard block after N in a window; keying on IP alone is the usual mistake (invariant 12) | 10 failures per (ip, identifier) per 15 min, with captcha engaging earlier at 3 |
| Where the revocation counter lives | account row | account row — one query already being read |
| Admin lifecycle | database-only / in-app with rank rules | see `admin.md` |

## 6. Gaps and design briefs

### auth.sso — design brief only; no worked example ships with this file

Audit trap worth knowing: a codebase that greps positive for "oauth" may have no sign-in flow at all. Service-account credentials for a cloud API are the usual false hit, and they are unrelated to user-facing SSO. Confirm an actual sign-in flow exists before recording this capability as anything but `todo`.

**Data.** An `identities` table, one row per external identity: `provider`, `subject` (the provider's stable user id — never the email), `email`, `email_verified`, `user_id`, `created_at`, `last_used_at`, with `UNIQUE (provider, subject)`. The account keeps its own row; an identity points at it. A user may hold several.

**Linking — the whole security of this feature.** Never auto-link a provider identity to an existing account on an unverified, or merely matching, email. That is the classic takeover: an attacker registers the victim's address at a provider that does not verify it, signs in, and is handed the account. Two sanctioned paths only: (a) the user is **already signed in** and explicitly links, or (b) the provider asserts `email_verified` **and** the address matches, **and** the user confirms on an interstitial that names the existing account. Everything else creates a new account.

**Flow.** Standard authorization code with PKCE. Generate `state` and `nonce` per attempt, store them server-side against the session, verify both on return, and expire them in minutes. Validate the ID token's signature, issuer, audience and `nonce` before reading a single claim. On success, establish the session through the *same* fixation-safe login the password path uses, so the revocation counter, the remember-me reset and the login stamp all happen exactly once (invariants 1, 3, 17).

**Redirect URIs are per environment and must be registered per environment**: local `https://<project>.localhost`, the private staging host, and production. ⚠️ Verify Google's current rules for non-public TLDs before assuming `.localhost` is registrable — if it is not, the local story is a loopback `http://127.0.0.1:<port>` redirect or a staging-only integration, and that is a decision to make *before* building.

**What the existing flows mean for a password-less account.** Decide all four up front, or they get decided by accident:
- *Change password* — offer "set a password" instead, which is a password *creation* flow and must still bump the counter and revoke tokens.
- *Forgot password* — must not silently do nothing. Answer the same neutral message, and email the address a "you sign in with <provider>" note (invariant 6 still applies).
- *MFA* — an SSO-only account's second factor is the provider's. Offering local TOTP on top is legitimate but means the login path has to run the challenge for a provider return too, which is a real branch, not a toggle.
- *Delete account* — unchanged; the identity rows go with it.

**Unlinking.** Refuse any unlink that would leave the account with **zero** login methods. Count "has a usable password" and "has ≥1 other identity"; if neither holds after the unlink, refuse and tell the user to set a password first.

**Apple specifics** (they surprise people): the user's name and email are returned **only on the very first consent** — persist them then or lose them; addresses may be private relays (`@privaterelay.appleid.com`), which are real deliverable addresses but change if the user disconnects the app, so never treat one as a stable identifier — `sub` is the identifier; Sign in with Apple requires a **paid developer membership** and a Services ID plus a key-signed client secret that expires and must be rotated. Budget for that before promising the button.

**Tokens.** Do not store provider access or refresh tokens unless a feature actually calls that provider's API on the user's behalf. If you must, they are secrets at rest under the environment key (invariant 15) and they are revoked with the identity.

**Tier 3** until a project needs it.

### account.settings — timezone (no implementation in any project)

A per-user timezone is routinely missing, and where streak or daily-activity logic already exists it typically runs on the **server's** date (`CURDATE()`) — so a user in another timezone loses a streak at the wrong hour and every "today" figure is wrong for them. Build it as: an IANA timezone string on the account, defaulted from a client-supplied guess at registration and editable in settings; every user-facing day boundary computed *in that zone*, while storage stays in the database's frame (invariant 8 is unchanged — one clock for expiry, a presentation zone for day boundaries). Do this before shipping streaks, daily goals or any per-day report, because retrofitting it means reinterpreting historical rows.

### account.management — active sessions list (no implementation)

Any project with remember-me already stores one row per remembered device (`auth_tokens`) with a `last_used_at`, and at least one already exports it in the GDPR bundle as `signed_in_devices` — but none offers "here are your signed-in devices, revoke one". The data exists; the surface does not. Build it as a read of that table plus a per-row revoke (delete the row) and a "sign out everywhere" (delete all **and** bump the counter — invariant 3). Cheap, and it is what a user reaches for after a scare.

### auth.core — a shared account library

This logic gets re-derived in a different shape in every codebase that needs it. When the next one does, the honest move is to lift the decision functions (password policy, identifier conflicts, session state) and the primitives (TOTP, crypto, rate limiter, remember-me) from wherever you already have them into the new project's own idiom rather than inventing another variant.

## 7. Manifest rows

| Capability id | Tier | Done means |
|---|---|---|
| `auth.core` | 1 | Register, login, logout and a session probe exist; sessions rotate on every privilege change; a revocation counter is stamped at login and checked on every authenticated request; the account status gate fails closed on a missing row and open on a DB error. |
| `auth.verify-email` | 1 | Hashed, expiring, single-slot token issued at registration and resendable under a throttle; the gate on unverified accounts is enforced server-side; the token's expiry is written and read by one clock (invariant 8). |
| `auth.password-reset` | 1 | Neutral response regardless of account existence; hashed 1-hour single-use token claimed under a row lock inside a transaction; success writes the password, burns every outstanding token for that user, revokes all devices and bumps the counter — or rolls back entirely. |
| `auth.password-policy` | 1 | One server-side policy function called at every password write site, enforcing a length floor and the 72-byte bcrypt ceiling. Any client-side meter is cosmetic. |
| `auth.remember-me` | 1 | Split selector/validator token, validator stored hashed and compared with `hash_equals`, capped per user, expired rows collected, revoked on logout and on every password/email/MFA change; theft (or the chosen non-rotating equivalent) is handled explicitly. |
| `auth.mfa` | 1 | TOTP enrolment that activates only on a confirmed live code; seed encrypted under an environment-held key; replay guarded by the last accepted step; hashed single-use recovery codes spent by a conditional write; a durable attempt budget the correct password cannot clear; re-authentication on every management action. |
| `auth.captcha` | 1 | Per-surface toggles, inert unless both keys are present, verified server-side, failing open on provider/our-side faults and closed only on a definite visitor fault; login challenges only above a failure threshold. |
| `auth.rate-limits` | 1 | One shared limiter whose decision is atomic and fails closed; login keyed on (ip, identifier); registration, reset-mail, MFA and every password re-authentication prompt all metered; the bucket namespace lives in a column no caller can forge. |
| `auth.sso` | 3 | `n/a` with a reason, or: identities table with `UNIQUE (provider, subject)`, PKCE + state + nonce verified, no auto-link on an unverified email, per-environment redirect URIs registered, and unlink refused when it would leave zero login methods. |
| `account.profile` | 1 | A signed-in user can see their identity, plan/entitlement state and recent activity on one page, served by one endpoint. |
| `account.management` | 1 | Change password (re-auth → revoke everywhere → re-establish this session from a fresh counter) and change email (verify-before-switch, both addresses notified, revoke everywhere on commit). Export and deletion entry points link to `privacy-legal.md`. |
| `account.settings` | 1 | Preferences and consent controls persist and are read back by the features that depend on them; a timezone exists before any per-day feature ships. |
