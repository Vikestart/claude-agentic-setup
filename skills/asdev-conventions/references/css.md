# CSS Patterns

One design system per app, hand-written, no preprocessor. The lint script (`lint_rules.py`) enforces the compact formatting — write it right the first time.

## Formatting rules (enforced)

- **<6 properties → one line, zero spaces** after `:` or between declarations:
  ```css
  .muted{color:var(--muted);font-size:0.9rem;}
  .hidden{display:none!important;}
  nav a.active{color:var(--primary);background:rgba(111,95,228,0.12);}
  ```
- **Multi-line (indented) only** for flex/grid layout blocks or 6+ properties:
  ```css
  .app-header {
      position:sticky; top:0; z-index:100;
      display:flex; align-items:center; justify-content:space-between;
      backdrop-filter:saturate(180%) blur(18px);
  }
  ```
  (Even multi-line keeps the `prop:value;` pairs space-free; several pairs may share a line when related.)
- Related selectors adjacent, grouped under section comments (`/* header */`, `/* services strip */`).
- **Media queries at the very bottom** of the sheet, largest breakpoint first — or, in multi-sheet projects, concentrated in a dedicated `responsive.css`.
- Kebab-case component/utility class names (`.btn-primary`, `.landing-hero`, `.custom-select-wrapper`) — not BEM, not utility-first frameworks.

## Token architecture

Everything themeable is a `:root` variable, grouped by concern (color / shape / elevation / motion / type):

```css
:root{
    --primary:#5b54e8;--primary-600:#4840c4;
    --radius:14px;--pill:999px;
    --shadow-md:0 6px 16px rgba(0,0,0,0.06),0 14px 36px rgba(0,0,0,0.07);
    --ease:cubic-bezier(0.4,0,0.2,1);--dur:0.22s;
    --font:'Plus Jakarta Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
}
```

- Reuse tokens in components; theme variants of a component through per-component custom props: `.btn-primary{--bg-btn:var(--primary);--fg-btn:#fff;}`
- Values that vary per-element go through inline custom props, not inline styles: `style="--build-stat:72%"` consumed by `width:var(--build-stat)`.
- Modern features are welcome where they degrade gracefully: `color-mix(in srgb, var(--surface) 78%, transparent)`, `backdrop-filter`, View Transitions.

## Theming (dark/light)

Class/attribute-based, **not** `prefers-color-scheme` alone — the user's apps persist an explicit choice (cookie/localStorage) so PHP can render the right theme with no flash:

- dark-first: tokens on `:root`, overrides under `html[data-theme="light"]{...}`
- light-first: the inverse, overrides under `[data-theme="dark"]{...}`
- named alternate theme: a body class (`body.alt-theme{...}`) re-declaring the same tokens

Whichever direction, the override block only re-declares tokens — components never know about themes.

## Fonts, icons, motion

- Fonts self-hosted as variable woff2 via `@font-face` (Space Grotesk, Plus Jakarta Sans, Nunito, Baloo 2...). **Every project self-hosts** — vendor the woff2 subsets you actually use rather than pulling from Google Fonts, so the CSP needs no third-party font origin.
- FontAwesome self-hosted (webfont/CSS flavor); icons via `<i class="fa-solid fa-...">`. Install it from a git-ignored source drop rather than committing the whole kit, emit only the families you use (`fa-solid`/`fa-brands`), and keep CDN origins out of the CSP — the aim is no third-party origin that is not deliberate.
- Always include a `prefers-reduced-motion` block neutralizing transitions/animations.
- `:focus-visible` ring on interactive elements; loading states via an `is-loading` class with an `::after` spinner.

## Performance habits (from Lighthouse work on a content-heavy PWA)

- Critical above-the-fold CSS inlined per-route; non-critical sheets deferred with the `media="print"` → flip-on-load trick.
- Single stylesheet per surface for small apps; split by feature area only when the app is large (~15 sheets in the biggest of these apps), keeping `variables.css` (tokens) and `responsive.css` (all media queries) separate.
- Cache-bust via `filemtime()` or a per-theme version constant (e.g. `THEME_VER`) — bump per release,
  never per-request randomness *(enforced: `convention_audit` RANDOM_CACHE_BUST)*.

## Documented breakpoints

- content-heavy site: `1420px` (small desktop), `1002px` (tablet/mobile), `800px` (extra small), plus 600/450px.
- admin theme: `1080px`, `768px`, `560px`.
- New projects: pick a similar 3-tier ladder and keep every query at the sheet bottom.

## Icon geometry (learned 2026-07-22 — recurring miscentering class)

FontAwesome **duotone** icons are TWO stacked glyph layers (`::before` + an absolutely-positioned
`::after`). Two rules keep them intact, and they are the root cause of every "icon looks broken /
off-center" report so far:

1. **Never `display:block` an icon** *(enforced: `lint_rules` CSS_ICON_BLOCK — it exempts a bare
   `<i>` that is a drawn shape — one declaring a background *or* an explicit box size, since bar
   charts and skeleton placeholders legitimately use block, and their colour often comes from a
   parent rule or an inline custom prop)*. The secondary layer pins to the box edge, so a full-width
   block tears the layers apart AND un-centers the glyph. A standalone icon (empty states, header
   art) is `display:inline-block` inside a `text-align:center` parent — the parent centers the box,
   the layers stay aligned. House examples: `.catalog-empty i` (correct original),
   `.support-empty i` (the fixed regression).
2. **Gradient-clipped headings mangle child icons.** `background-clip:text` +
   `-webkit-text-fill-color:transparent` INHERIT into a child `<i>` and paint duotone layers with
   the clipped gradient ("missing piece" look). Any icon inside such a heading needs its own
   `-webkit-text-fill-color:<color>` to re-opaque it (see `.compact-header-text h1
   .icon-container`).

**Verification habit:** any new standalone/decorative icon gets a browser look (screenshot or a
computed-style check for the centering) before shipping — structure-only checks miss geometry.

## Save feedback (2026-07-22)

Save/apply confirmations in Profile + Admin are **lower-right toasts** via `assets/js/toast.js`
(`toastSuccess`/`toastError`) — never inline "Settings saved." spans. Inline
messages remain only for content that must persist or sit next to its context: validation errors,
editor save-warnings, progress states.
