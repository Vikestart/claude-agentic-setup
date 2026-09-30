---
name: asdev-release
description: Take finished, locally validated work through staging to production — syncing `main` and `staging` once per release task, pre-flight checks (version bump, migrations, owner actions), merging, validating each environment, rollback, when to pause, and aligning branches after a PR merged on GitHub. Use before merging into `staging` or `main`, before any deploy, when the owner says a PR was merged, or when a plan's Release step starts. Not for planning a phase (asdev-planner) or for the local audit gate (asdev-web-audit).
---

# Releasing

CLAUDE.md §2 holds the branch model — `main` is production, `staging` the one shared development
branch, never push directly to `main` — and §1 says what an approved plan covers. This skill is how
a release runs.

**The goal:** production runs exactly what was validated on staging, and the owner can read the
true state of every environment from your report without checking anything themselves.

## 0. Know this project's release shape

Projects differ in branch names, in what fires a deploy and in what the deploy runs. Before touching
a branch, read the project's own `AGENTS.md` / `CLAUDE.md` (a closer file wins over this skill) and,
if present, the per-project cheat sheet in `asdev-conventions/local/projects.md`. Establish:

- which branch deploys production, and whether a push or a merge fires it;
- whether staging is a separate deployed environment, and how to reach it;
- what the deploy runs besides pulling code (a migration hook, a cache clear, a build of nothing);
- how the running version can be read (a footer badge, a version or health endpoint).

If the project names none of this, ask once rather than guessing — a wrong guess here deploys.

## 1. Pre-flight — before any merge

- **Local validation passed**, and its scope was printed: a battery that silently skipped suites can
  exit 0. Run `audit_all.py --since main` for release scope (the `asdev-web-audit` skill).
- **Version bumped** where the project has a version constant, in lockstep with any client cache
  key it gates (a service-worker `CACHE_NAME`, an asset version). A minimum-version floor must never
  exceed the current version, or clients loop between "update" and "still below minimum".
- **Migrations are additive and idempotent** if a deploy hook runs them. The hook runs *after* the
  new code is live, so for a while new code talks to the old schema. Anything that can change or
  destroy existing data takes a separate, owner-approved path with a backup first — never the deploy
  hook. A large or contended table is rehearsed on a disposable copy first.
- **Owner actions listed:** new environment variables or secrets on the server, webhooks, vhosts,
  cron entries, DNS. You cannot do these; name each one before the merge, not after a failure.
- **Release proof script:** if the project has one (e.g. `scripts/release_proof.py`), it is the
  standard check at each stage — version, health, deploy marker, assets identical to the branch — and
  its verdict replaces the manual checks of those four things only. Flow checks, the secrets check,
  environment targeting and migration confirmation below still run. A project releasing often without one should get
  one (a procedure done twice becomes a script).
- **No secrets or debug output in the diff** (`git diff main...staging`).

## 2. Sync the branches — once per release task, not every phase

1. Preserve uncommitted work (commit it if it is finished and yours; otherwise leave it untouched
   and say so).
2. `git fetch origin`.
3. Fast-forward local `main` and `staging` to their remotes.
4. Merge the updated `main` into `staging`.

On divergence or a conflict, **stop and report** the exact state. Never invent a branch, force-push,
or discard work to get past it.

## 3. Staging

Push `staging` and let it deploy. Then validate on staging itself, not on local:

- the health or liveness endpoint answers;
- the running version is the one just shipped — a cached page or a stale service worker can show
  the old build while the new one is live;
- each flow the change touched works, at the viewports it affects, with no new console errors;
- server-side commands target staging explicitly. A bare CLI on a shared host can read the
  production environment file — prefix staging commands with whatever the project uses to select
  the staging environment.

Fix ordinary in-scope failures on `staging` and re-validate. Do not move on with a known failure.

## 4. Production

- Merge `staging` into `main` and push. Never commit on `main` directly.
- **Confirm the deploy happened**, not merely that the push succeeded: a webhook can answer `200`
  for work it never did. Read the running version on the live site.
- Validate the changed flows read-only. Do not create test accounts, orders or content on
  production; if a flow can only be proved by writing, say so and leave it to the owner.
- If the deploy ran migrations, confirm they applied (the project's status or `--verify` mode).

## 5. When production is wrong

- **Code:** revert the offending commit on `staging`, validate, merge forward to `main`. Never
  force-push or reset `main`.
- **Data:** git cannot undo a migration or a data change. That is why data-risky changes need a
  backup first; restoring one is an owner decision — stop and report.
- **Deploy did not fire, or half-applied:** stop and report the exact state; re-triggering a hook or
  running server commands by hand is outside a normal release.

## When the owner says a PR was merged on GitHub

Run `git fetch origin main:main` first, to align the local branch and clear the diff cache, before
reading any diff or state.

## Pause only for

- a material scope or product decision;
- missing authority or credentials;
- an irreversible action outside the plan;
- a security, privacy or data risk outside the plan;
- a branch or environment conflict;
- an unresolved blocker.

Everything else — an ordinary in-scope failure, a routine transition between stages — you handle
and carry on.

## Report

Whenever you stop, and at the end, give the lifecycle state, each item verified rather than assumed:

| | State | Verified by |
|---|---|---|
| Local | committed · uncommitted files | `git status` |
| Staging | pushed at `<sha>` · running version | `<endpoint or page>` |
| Production | merged at `<sha>` · running version | `<endpoint or page>` |

Then the owner actions still pending, and anything validated only partly and why.
