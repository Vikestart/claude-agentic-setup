---
name: asdev-conventions
description: House style for the user's dependency-free vanilla web projects (PHP 8+, native ES modules, hand-written CSS, no framework or build step). Read it when starting PHP, JS, CSS or HTML work in one of them — features, endpoints, routes, components, styling, theming — or scaffolding a project, or when the user mentions house style or conventions.
---

# Web Development House Conventions

*Plain markdown — any AI coding agent can read this directly; nothing here depends on a particular
vendor or harness.*

**One philosophy: dependency-free vanilla code with no build step.** Plain PHP 8+, ES6+ modules
loaded natively, hand-written CSS. No frameworks, no Composer packages, no npm, no bundler. Adding a
dependency is an architectural decision the user makes, never a convenience default.

**How much of this to apply.** Read it once when you start work in a project; it holds for the
session. Then **match the surrounding code** — naming, formatting, layout and idiom are learned
faster and more accurately from the file you are editing than from any description of them. This
document carries only what reading the code cannot teach: the traps below, the choices that look
arbitrary until they break, and the deep references for first-of-kind work with nothing to imitate.

## What imitation cannot teach

- **Never `display:block` a FontAwesome icon.** Duotone glyphs are two stacked layers, and block
  tears them apart and un-centers the glyph; standalone icons are `inline-block` inside a
  `text-align:center` parent. This is the root cause of every "icon looks broken" report so far, and
  it matters most because the correct code looks arbitrary — an agent tidying it reintroduces the
  bug. Full rule and house examples in [references/css.md](references/css.md). *(enforced:
  `lint_rules` CSS_ICON_BLOCK)*
- **Gradient-clipped headings mangle child icons.** `background-clip:text` +
  `-webkit-text-fill-color:transparent` inherit into a child `<i>` and repaint the glyph layers with
  the clipped gradient; such an icon needs its own `-webkit-text-fill-color`. Too judgement-heavy to
  scan — give any new decorative icon a browser look, since structure-only checks miss geometry.
- **Comment the *why*, never the *what* — and do not imitate comment density.** This is the one
  place "match the surrounding code" actively misleads: the codebase runs ~18% comment lines, and
  its longest file headers earn every line, because each records something that went wrong once —
  a lock namespace that stalled a deploy for 900 seconds, a webhook that returned `200` for work it
  never did. **Never "tidy" those.** They are also not a template. A new function needs no docblock
  restating its signature and no `@param` repeating a type the signature already gives. Durable
  architecture, contracts and migration history belong in `.docs/reference/`; a comment in code
  carries only what someone *changing this code* would otherwise get wrong. The test before writing
  one: would deleting this line let a careful reader make a mistake? If not, do not write it.
- **When two of the user's own idioms conflict, prefer the newer, stricter one for new files — but
  never mix idioms within a project.** "Match the surrounding code" gives no answer when the
  surroundings disagree; this is the tie-break.
- **Self-host everything for CSP** — fonts (variable woff2), FontAwesome, libraries; no third-party
  origin that is not deliberate. FontAwesome Pro where licensed, free tier otherwise: follow
  whatever that project already loads. Never base64 or drawn SVG in code: an icon file used as a
  sprite is referenced with `<svg><use href="sprite.svg#name"></use></svg>`, which is allowed
  (the scanner skips it; a drawn shape beside it is still flagged).
- **Cache-bust with `filemtime()` or a release version constant**, never per-request randomness —
  that busts the cache on every request, which is the opposite of the point. *(enforced:
  `convention_audit` RANDOM_CACHE_BUST)*
- **Save/apply confirmations use the project's toast component** (lower-right, auto-dismiss), never
  inline "Saved" spans. Inline messages stay for validation errors and persistent warnings.

## Match the project, not a canon

Projects intentionally differ on DB layer, API shape and theming. **Before writing backend code or
picking a pattern, establish which project and which file you are in**, then mirror it. Where the
optional `local/` overlay exists, its router answers that directly and names the exact references to
read:

```bash
python "<this-skill>/local/project_context.py" --path <project-dir> --changed
```

(`local/project-context.ps1` is the PowerShell equivalent; `local/projects.md` is the full
cross-project cheat sheet, for when the router is inconclusive or work spans projects.) **Without a
`local/` directory everything here stands on its own** — the normal state on any machine but the
author's.

## Deep references — read only what the task needs

- [references/php.md](references/php.md) — endpoint skeletons per project style, session/auth/
  remember-me patterns, security invariants.
- [references/js.md](references/js.md) — router and route-table patterns, the CSRF-aware fetch
  wrapper, store/optimistic UI, delegation idioms, service-worker versioning.
- [references/css.md](references/css.md) — formatting rules with examples, token architecture,
  theming, breakpoints, the full icon-geometry rules.

## A project's CLAUDE.md / AGENTS.md

**A project's `CLAUDE.md` / `AGENTS.md` stays under ~20 kB and 100 lines.** It is re-read every turn there, and past a point the rules that matter drown — the limit is attention, not disk. When it outgrows that, split it as nebulingo was: a short core (invariants, environment, routing) plus one `.docs/reference/` file per system, read only when that system is touched; never re-inline them. The global `~/.claude/CLAUDE.md` is exempt.

## Where the rules live

Security fundamentals, planning gates, the `.docs/` layout, Git topology and verification
proportionality are owned by the global instruction files — follow them from there; this skill does
not restate them. Deterministic conformance belongs in the `asdev-web-audit` scanners: when a prose
convention can be checked with acceptably low false positives, add or improve a canonical audit rule
rather than keeping a second copy here. Judgement-heavy design choices stay in the references above.
One skill-local note: when the aggregate audit gate runs, do not repeat its syntax checks separately.
