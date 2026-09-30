# <Project> — Current handover

**As of <YYYY-MM-DD>.** The entry point for a fresh session, with [roadmap.md](roadmap.md),
[task.md](task.md) and [walkthrough.md](walkthrough.md).

**No phase is active.** Phase 0 (platform foundation) is complete locally; nothing is deployed.

## State

- Environments: local only. Staging and production vhosts are owner actions pending — see
  [reference/platform-manifest.md](reference/platform-manifest.md) "Owner actions pending".
- Database: `<project>_dev` on `127.0.0.1`, seeded by the baseline migration.

## Decisions taken

- Idiom: <REST front controller | action-dispatch | modular CMS>, because <reason>.
- Tier-3 profile: <billing / gamification / teams / SSO / email admin — yes/no each, with reasons>.

## Next steps

1. Owner actions (staging vhost, deploy keys + webhooks, Tailscale lock, DNS, server-level deny).
2. Tier 1 — start with `auth.core` (identity.md in the skill).
