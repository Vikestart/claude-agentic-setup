# <Project> — Project Architecture & Constraints

*Global web-dev rules (dependency-free vanilla stack, strict native PHP types, no frameworks, the
`.docs/` workflow, git/deploy topology) are inherited from the global config and the
`asdev-conventions` skill. This file is <Project> domain logic and the facts that differ per project.
It is a MAP — keep it short and point into `.docs/reference/` for the reasoning.*

## What this is
<One paragraph: what the product does, who uses it, what category it is in and is NOT in.>

## Deep references — READ THE MATCHING FILE BEFORE TOUCHING THAT SYSTEM
- [.docs/reference/platform-manifest.md](.docs/reference/platform-manifest.md) — which platform
  capabilities exist, which are deferred and why. Maintained through the `asdev-blueprints` skill.
- <[.docs/reference/<area>.md] — one line per deep reference: what it covers and which paths trigger it.>

## Environments
| | Local | Staging | Production |
|---|---|---|---|
| URL | `https://<project>.localhost` | `https://staging.<domain>` — **tailnet-only** | `https://<domain>` |
| Branch / deploy | working tree | push to `staging` → webhook deploy (never production) | merge `staging` → `main` → webhook deploy; never push `main` |
| Database | `<project>_dev` on `127.0.0.1` | `<project>_staging` on the VPS | `<project>` on the VPS |
| Secrets | root `.env` (git-ignored) | <per-environment secret file or path> | <per-environment secret file or path> |
| Indexing | — | `X-Robots-Tag: noindex` on every response | indexable |

- `APP_ENV` ↔ `DB_NAME` disagreement is reported at boot. An unstated `DB_HOST` resolves to loopback
  and nothing else. <Adjust to the project's actual routing once built — see foundation.md in the skill.>
- Provider keys: sandbox on local + staging, live ONLY in production's secret file.

## Architecture (orientation)
- **Routing:** <front controller / action-dispatch / CMS router — one line, with the file>.
- **API shape:** <JSON envelope, CSRF rule, auth gate order — one line each>.
- **Views / JS entry / CSS:** <one line each; the house patterns are in asdev-conventions>.
- **Global state / boot gotchas:** <only what a new session will get wrong>.

## API & database
- All queries through `<db layer>`; prepared statements; transactions for multi-row writes.
- **Schema changes live ONLY in `<migrations location>`** and follow the migration approval rule:
  additive + idempotent ships; anything that can change or destroy existing data needs explicit owner
  approval and never rides the deploy hook.
- Scanner findings that are BY DESIGN are recorded in `.audit-baseline.json` with their reason, not here.

## Testing scope
- `<release gate command>` is the release gate. <Scope flags, the DB-suite rule, CI jobs — link
  `.docs/reference/testing.md` once it exists.>

## Versioning
- Bump `<APP_VERSION constant/file>` (and `<CACHE_NAME>` in lockstep if a service worker exists) on
  any cached-asset change.

## Hard prohibitions
- <Project-specific never-do items. Examples from sibling projects: "asset sync is admin-panel only";
  "payment provider named in the Privacy Policy must match the billing code".>
