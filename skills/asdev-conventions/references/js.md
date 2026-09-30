# JavaScript Patterns

Native ES modules, no build step, no jQuery, no inline handlers. Files small and single-purpose (`components/toast.js`, `modules/filters.js`); split anything nearing 50 KB / 1k lines.

## SPA router + route table (front-controller style — default for new projects)

```js
router
  .on('/dashboard', (ctx) => view('./modules/dashboard.js', 'renderProjects', ctx), { shell: 'app', auth: true })
  .on('/share/:token', (ctx) => view('./modules/share.js', 'renderShare', ctx), { shell: 'bare' });

async function view(modulePath, fn, ctx, arg) {
  const mod = await import(modulePath);           // lazy: route code loads on first visit
  mod[fn](ctx.outlet, ctx.params, arg);
}
```

- History API navigation; internal `<a href="/...">` intercepted by a delegated listener (skip URLs whose last segment contains a `.` — real files). A variant marks internal links with `data-link` instead and routes through `navigateTo(url)` — never `window.location` for internal nav.
- Wrap view swaps in `document.startViewTransition(() => ...)` when available, plain swap otherwise.
- Conditional loading on non-SPA pages: `if (el('#filterable-mission-list')) import('./modules/filters.js').then(m => m.initFilters());`

## The fetch wrapper — one network path per app

Every project funnels requests through a single wrapper; never scatter raw `fetch` calls in new code (older code in these projects does — don't copy that).

`api.js` essentials: same-origin credentials, auto `X-CSRF-Token` on mutations, JSON bodies, typed `ApiError` carrying `status`, and a one-shot CSRF self-heal:

```js
if (res.status === 403 && MUTATING.has(method) && /csrf/i.test(data?.error || '')) {
  const me = await (await fetch('/api/auth/me', { credentials: 'same-origin' })).json();
  if (me?.csrf_token) { store.set({ csrf: me.csrf_token }); ({ res, data } = await send(path, method, body)); }
}
export const api = { get: (p) => request(p), post: (p, b) => request(p, { method: 'POST', body: b }) /* ... */ };
```

Other flavors: an admin-panel wrapper `api(endpoint, action, payload)` (FormData + a custom SPA header, 401 → login redirect, exporting `toast`/`confirmDialog`/`escapeHtml`); and a localhost-tool wrapper `post(url, body)` that attaches `csrf` + an unlock token, opens the unlock modal and retries once on a `locked` response, sends `URLSearchParams` bodies and `cache: 'no-store'`.

## State, optimistic UI, delegation

- A small reactive `store.js` singleton caches the authed user at boot (`isAuthed`/`isPro` getters) so navigation never re-fetches auth.
- Mutations are optimistic: update the local array/DOM immediately, call the API, roll back and toast on failure.
- One document-level delegated listener routes UI actions: `document.addEventListener('click', e => { const btn = e.target.closest('[data-action]'); if (btn) actions[btn.dataset.action]?.(btn, e); });` Dynamic elements need zero listener wiring.
- Escape untrusted text client-side with an `escapeHtml` helper (detached-div or replace-map) or assign via `textContent`. CSP forbids inline/eval — keep all JS in module files.
- Vanilla DOM toolkit precedent (`core/dom.js`, ~40 lines): `el`/`els`, `on`, `delegate(root, type, selector, handler)`, `show/hide/toggle`, Promise-returning fades/slides via the Web Animations API, `getText`/`postJson` helpers. Write small helpers like this instead of importing a library.

## Boot discipline

- **Boot-once guards** for modules that might be injected twice: check a namespaced flag (`window.__app.routerBooted`) and go inert on second load.
- **Late-load safety**: when modules load after DOMContentLoaded (one app injects the router after first contentful paint), don't blindly wait for the event — `if (document.readyState !== 'loading') init(); else document.addEventListener('DOMContentLoaded', init);`
- Global runtime state lives under ONE namespace object per app (`window.__app = window.__app || {}`); loose `window.foo` globals are forbidden.
- Long-running client operations that must not be interrupted by a service-worker auto-reload use a ref-counted busy flag the SW update code respects.

## Service workers

- Versioned `CACHE_NAME` (`'app-v2'`, `'dash-v5'`) bumped every release — and where the app has one, in lockstep with the `APP_VERSION` constant, so a stale cache cannot outlive a deploy.
- Two working strategies: network-first with `{cache: 'no-cache'}` plus `skipWaiting()` + `clients.claim()` for auto-update; or stale-while-revalidate for static assets with network-first navigations. Either way, **bypass** admin and action paths entirely.
- Never let a SW cache mutating endpoints or auth pages.
