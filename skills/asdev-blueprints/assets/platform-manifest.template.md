# <Project> — platform manifest

*Maintained through the `asdev-blueprints` skill. One row per platform capability. The skill's
**audit** mode rewrites this file; its **build** mode updates one row; the scaffold writes the first
version. Status vocabulary: `done` · `partial` · `todo` · `deferred` · `n/a`. A `deferred` or `n/a`
row MUST carry a reason — an unexplained gap is exactly the failure this file exists to prevent.
"Done" for each id is defined in §7 of the matching reference file in the skill.*

**As of:** <YYYY-MM-DD> · **Audited against skill version:** <asdev-blueprints commit/date>

**Tier-3 profile (decided at scaffold, revisited at audit):** billing <yes/no> · referrals <yes/no> ·
gamification <yes/no> · teams <yes/no> · SSO <yes/no> · email administration <yes/no> ·
PWA <yes/no> · admin i18n <yes/no>

**Idiom:** <REST front controller | action-dispatch | modular CMS>

## Tier 0 — before the first push to staging

| Capability | Status | Reason / notes | Ported from | Decisions |
|---|---|---|---|---|
| `env.secrets` | todo | | | |
| `env.environments` | todo | | | |
| `env.staging-lock` | todo | owner action: Plesk vhost, Tailscale, DNS | | |
| `docs.layout` | todo | | | |
| `http.deny` | todo | owner action: server-level nginx/Apache directives | | |
| `http.headers` | todo | | | |
| `release.versioning` | todo | | | |
| `db.migrations` | todo | | | |
| `db.backups` | todo | owner action: scheduled task, BACKUP_DIR outside docroot | | |
| `test.battery` | todo | | | |
| `ops.health` | todo | | | |
| `mail.transport` | todo | | | |

## Tier 1 — before the first real user

| Capability | Status | Reason / notes | Ported from | Decisions |
|---|---|---|---|---|
| `auth.core` | todo | | | |
| `auth.verify-email` | todo | | | |
| `auth.password-reset` | todo | | | |
| `auth.password-policy` | todo | | | |
| `auth.remember-me` | todo | | | |
| `auth.mfa` | todo | | | |
| `auth.captcha` | todo | | | |
| `auth.rate-limits` | todo | | | |
| `account.profile` | todo | | | |
| `account.management` | todo | | | |
| `account.settings` | todo | | | |
| `admin.panel` | todo | | | |
| `admin.rbac` | todo | | | |
| `admin.users` | todo | | | |
| `admin.settings` | todo | | | |
| `admin.kill-switches` | todo | | | |
| `admin.audit-log` | todo | | | |
| `admin.dashboard` | todo | | | |
| `privacy.consent` | todo | | | |
| `privacy.export` | todo | | | |
| `privacy.deletion` | todo | | | |
| `privacy.retention` | todo | | | |
| `legal.pages` | todo | | | |
| `legal.reconciliation` | todo | | | |
| `notify.user` | todo | | | |
| `notify.admin` | todo | | | |
| `notify.email` | todo | | | |

## Tier 2 — before public launch

| Capability | Status | Reason / notes | Ported from | Decisions |
|---|---|---|---|---|
| `mapi.credentials` | todo | | | |
| `mapi.gates` | todo | | | |
| `mapi.read` | todo | | | |
| `mapi.schema` | todo | | | |
| `mapi.work` | todo | | | |
| `mapi.test-accounts` | todo | | | |
| `mapi.ip-allowlist` | todo | | | |
| `mapi.openapi-clients` | todo | | | |
| `support.public` | todo | | | |
| `support.user` | todo | | | |
| `support.admin` | todo | | | |
| `support.attachments` | todo | | | |
| `seo.core` | todo | | | |
| `search.core` | todo | n/a if there is nothing to search — say so | | |

## Tier 3 — where applicable

| Capability | Status | Reason / notes | Ported from | Decisions |
|---|---|---|---|---|
| `billing.provider` | todo | | | |
| `billing.plans` | todo | | | |
| `billing.webhooks` | todo | | | |
| `billing.entitlements` | todo | | | |
| `billing.referrals` | todo | | | |
| `auth.sso` | todo | no reference implementation yet — see identity.md §6 | | |
| `support.email` | todo | see support.md §6 | | |
| `game.xp-levels` | todo | | | |
| `game.achievements` | todo | | | |
| `game.streaks` | todo | | | |
| `teams.workspaces` | todo | pattern only | | |
| `integrations.webhooks` | todo | pattern only: outbound webhooks | | |
| `pwa.service-worker` | todo | pattern only; deliberately absent is a valid answer | | |
| `admin.i18n` | todo | pattern only: admin i18n | | |

## Owner actions pending

*Things the scaffold or a build could not do because they live outside the repository (Plesk panel,
DNS, provider dashboards, scheduled tasks). Remove a line when it is verified done.*

- <none recorded>

## Audit history

| Date | Mode | Report | Summary |
|---|---|---|---|
| <YYYY-MM-DD> | scaffold | — | first manifest |
