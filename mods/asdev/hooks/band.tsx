import { atom, read, update } from 'claude-code'
import type { EngineInterface as Engine, Register, SessionRateLimit } from 'claude-code'
import { asTimes, CACHE_STORE, CACHE_TTL, TRIGGER_FROM } from './compaction'

// Compaction lands about 33k below the window (measured 2026-10-01, main chats and agents alike).
const COMPACT_MARGIN = 33_000
const WINDOW_MS: Record<string, number> = { five_hour: 5 * 3600_000, seven_day: 7 * 86400_000 }
const LIMIT_NAME: Record<string, string> = { five_hour: '5 hours', seven_day: 'Week' }
const LIMIT_LABEL: Record<string, string> = { five_hour: '5h', seven_day: 'Week' }
// Enterprise replaces Team's two windows with a monthly quota (owner, 2026-10-21). No monthly kind is
// documented yet, so a gateway's spend_limit and any kind naming a month are taken as monthly until
// the kinds stored under `kindsSeen` say otherwise.
const isMonthly = (kind: string) => kind === 'spend_limit' || kind.includes('month')
const limitName = (kind: string) => LIMIT_NAME[kind] ?? (isMonthly(kind) ? 'Month' : kind)
const limitLabel = (kind: string) => LIMIT_LABEL[kind] ?? (isMonthly(kind) ? 'Month' : kind)
// A monthly window is the calendar month that ends at its reset.
function windowMs(kind: string, resets: number): number | undefined {
  if (WINDOW_MS[kind] || !isMonthly(kind) || Number.isNaN(resets)) {
    return WINDOW_MS[kind]
  }
  const start = new Date(resets)
  start.setUTCMonth(start.getUTCMonth() - 1)
  return resets - start.getTime()
}
const hasReset = (r: SessionRateLimit, now: number) => Date.parse(r.resetsAt ?? '') <= now
// The limits to show. The kept figures are the newest any session saw or the usage endpoint gave, so a
// kept figure of a kind this session reports wins unless its window has reset. Once the session has
// replied, a kind it does not report is gone (Team's windows after the move to Enterprise); before that
// the kept ones stand in, one whose window has reset drawn empty until the next read rather than
// dropped, so an idle chat's bars do not vanish (owner, 2026-10-30).
function pickLimits(own: SessionRateLimit[], kept: SessionRateLimit[], replied: boolean, now: number): SessionRateLimit[] {
  if (!replied) {
    return kept
  }
  return own.map(r => kept.find(x => x.kind === r.kind && !hasReset(x, now)) ?? r)
}

// Enterprise reports no window: its monthly spend limit is the account figure the app's usage panel
// shows, read where the engine reads it (amounts in cents; engine schema, 2.1.304). Fetched from a
// measure at most every few minutes, failures too, never from a draw.
const USAGE_URL = 'https://api.anthropic.com/api/oauth/usage'
const USAGE_EVERY = 2 * 60_000
// With no replies here the usage windows still move (another chat, claude.ai, the phone); once the last
// read is this old, the minute tick reads again. The try is shared, so all sessions together read at most
// this often (owner, 2026-10-30; it was 12 hours while only the month's spend was read).
const USAGE_IDLE = 5 * 60_000
// A kept window figure younger than this is drawn as current, not faint as the last known.
const LIMITS_FRESH = 3 * USAGE_IDLE
// The same reply carries the usage windows: utilization in percent, resets_at an ISO time or null
// before the window's first use; a window set to null is one the account does not have.
const WINDOWS = ['five_hour', 'seven_day']
// Python's six-digit fractions, cut to the three every Date parser takes.
const iso = (v: unknown) => {
  const t = typeof v === 'string' ? Date.parse(v.replace(/(\.\d{3})\d+/, '$1')) : NaN
  return Number.isNaN(t) ? undefined : new Date(t).toISOString()
}
// The newest figure wins, whichever way it came (owner, 2026-10-30): a reply's headers keep the figure
// until a later read, and a read is dated when it was asked, so a reply that lands while it is out wins.
async function keepWindows($: Engine, body: Record<string, unknown>, asked: number): Promise<string> {
  if (!WINDOWS.some(kind => kind in body)) {
    return 'no windows'
  }
  const at = await $.store.get('limitsAt')
  if (num(at) && at > asked) {
    return 'older than a reply'
  }
  const kept = ((await $.store.get('limits')) as SessionRateLimit[] | undefined) ?? []
  const got = new Map(Array.isArray(kept) ? kept.map(r => [r.kind, r]) : [])
  for (const kind of WINDOWS.filter(kind => kind in body)) {
    const w = body[kind] as { utilization?: unknown; resets_at?: unknown } | null
    if (!w) {
      got.delete(kind)
    } else if (num(w.utilization)) {
      got.set(kind, { kind, percentUsed: Math.round(w.utilization * 10) / 10, resetsAt: iso(w.resets_at) })
    }
  }
  await $.store.set('limits', [...got.values()])
  await $.store.set('limitsAt', asked)
  return 'ok'
}
const USAGE_WAIT = 10_000
// The daily allowance keeps 5% back, so what goes unspent builds a buffer (owner, 2026-10-26).
const DAY_SHARE = 0.95
// Today's pace runs over the working hours, in the system's own time zone, not over the whole day:
// at 10:00 a midnight-based pace would already read 42% (owner, 2026-10-27).
const WORK_FROM = 8, WORK_TO = 16
type Month = { used: number; limit: number; at: number; currency: string }
type DayStart = { day: string; used: number }
const num = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
// The store answers whatever a key holds (a test's mock one value for every key), so a figure counts
// only in its own shape.
const asMonth = (v: unknown): Month | undefined => {
  const m = v as Month
  return m && typeof m === 'object' && num(m.used) && num(m.limit) && num(m.at) && m.used >= 0 && m.limit > 0
    && typeof m.currency === 'string' ? m : undefined
}
const asDay = (v: unknown): DayStart | undefined => {
  const d = v as DayStart
  return d && typeof d === 'object' && typeof d.day === 'string' && num(d.used) ? d : undefined
}
// Days, weekdays and months follow the runtime's local zone.
const dayOf = (t: number) => {
  const d = new Date(t)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
const sameMonth = (a: number, b: number) => dayOf(a).slice(0, 7) === dayOf(b).slice(0, 7)
// Mon-Fri from day `from` to the month's end, that day included; public holidays are not known.
function workDays(year: number, month: number, from: number): number {
  let n = 0
  for (let d = from, end = new Date(year, month + 1, 0).getDate(); d <= end; d++) {
    const w = new Date(year, month, d).getDay()
    n += w > 0 && w < 6 ? 1 : 0
  }
  return n
}
// What today may spend: what the month had left when today began, over the working days left. A
// weekend counts none, so it shows the next working day's share; a weekend that ends the month shows
// the next month's first.
function allowance(m: Month, start: number, now: number): number {
  const d = new Date(now), y = d.getFullYear(), mo = d.getMonth()
  const days = workDays(y, mo, d.getDate())
  return DAY_SHARE * (days ? Math.max(0, m.limit - start) / days : m.limit / workDays(y, mo + 1, 1))
}
const dollars = (n: number) => `$${Math.round(n).toLocaleString('en-US')}`
const cents = (n: number) => `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

// A read stuck past this (the credential or the store, not only the fetch) stops blocking the next.
const USAGE_BUSY = 3 * USAGE_WAIT
let fetching = 0
// Reads the account figure into the store: `month` in dollars, or null when the read fails (no row then),
// `monthStatus` saying why, and `dayStart`, the first figure of each local day (again after a fall, a
// new month's reset).
async function refreshMonth($: Engine, now: number, every = USAGE_EVERY): Promise<void> {
  const tried = await $.store.get('monthTry')
  // Either way round: a clock moved back must not stop the fetches until it catches up.
  if ((fetching && Math.abs(now - fetching) < USAGE_BUSY) || (num(tried) && Math.abs(now - tried) < every)) {
    return
  }
  fetching = now
  let month: Month | null = null
  let status = 'unknown'
  try {
    const auth = await $.session.authorize()
    // A session without the account's own login says nothing about its spend: it leaves the figure, and
    // the 5-minute slot, to the sessions that have one.
    if (auth?.kind !== 'bearer') {
      await $.store.set('monthStatus', auth ? 'api-key' : 'no credential')
      return
    } else {
      await $.store.set('monthTry', now)
      const res = await Promise.race([
        $.http.fetch(USAGE_URL, { headers: { 'anthropic-beta': 'oauth-2025-04-20' }, auth: auth.handle }),
        $.clock.sleep(USAGE_WAIT).then(() => undefined),
      ])
      status = res ? String(res.status) : 'timeout'
      const body = res?.ok ? JSON.parse(res.text) as Record<string, unknown> : undefined
      const x = body?.extra_usage as Record<string, unknown> | undefined
      if (body && typeof body === 'object') {
        status = !x ? 'no extra_usage' : x.is_enabled !== true ? 'not enabled' : 'ok'
        await $.store.set('limitsStatus', await keepWindows($, body, now))
      }
      if (x && x.is_enabled === true) {
        // Raw numbers only: Number() would read a null or an empty string as 0 and start the day there.
        month = num(x.used_credits) && num(x.monthly_limit)
          ? asMonth({ used: x.used_credits / 100, limit: x.monthly_limit / 100, at: now, currency: String(x.currency ?? 'USD') }) ?? null
          : null
        status = month ? status : 'bad figures'
      }
    }
  } catch (err) {
    status = `error: ${String(err).slice(0, 80)}`
  } finally {
    fetching = 0
  }
  await $.store.set('month', month)
  await $.store.set('monthStatus', status)
  if (month) {
    const day = asDay(await $.store.get('dayStart'))
    if (!day || day.day !== dayOf(now) || month.used < day.used) {
      await $.store.set('dayStart', { day: dayOf(now), used: month.used })
    }
  }
  $.ui.invalidate('ui.render')
}

// The Today and Month rows from the kept figure; none without one, or with one from an earlier month.
function monthRows(m: Month | undefined, d: DayStart | undefined, now: number): Row[] {
  if (!m || !sameMonth(m.at, now)) {
    return []
  }
  // No figure yet today: today began where the last one stood.
  const start = d?.day === dayOf(now) ? d.used : m.used
  const may = allowance(m, start, now)
  const spent = Math.max(0, m.used - start)
  const over = spent > may
  const share = may ? spent / may : 1
  const d0 = new Date(now), first = new Date(d0.getFullYear(), d0.getMonth(), 1).getTime()
  const pace = (now - first) / (new Date(d0.getFullYear(), d0.getMonth() + 1, 1).getTime() - first)
  const ahead = m.used / m.limit > pace
  const hour = d0.getHours() + d0.getMinutes() / 60
  const dayPace = Math.min(1, Math.max(0, (hour - WORK_FROM) / (WORK_TO - WORK_FROM)))
  const asOf = new Date(m.at).toTimeString().slice(0, 5)
  const unit = m.currency === 'USD' ? '' : ` ${m.currency}`
  return [{
    name: 'Today',
    label: 'Today',
    used: share,
    ticks: [{ at: dayPace, red: share > dayPace }],
    pace: dayPace,
    ahead: over,
    // A share beside the bar, the dollars in the hover card: dollars wrapped the band (owner, 2026-10-27).
    value: `${Math.round(share * 100)}% / ${Math.round(dayPace * 100)}%`,
    detail: `${dollars(spent)} of ${dollars(may)}`,
    alt: `pace ${Math.round(dayPace * 100)}%` + (over ? ', past today\'s allowance' : ''),
    // Kept to the figure and what the two numbers mean: the allowance's rule is at DAY_SHARE (owner, 2026-10-27).
    tip: `${cents(spent)} of ${cents(may)}${unit} today (as of ${asOf})`
      + ` · allowed: the month's remaining budget over the working days left`
      + ` · second figure and arrow: ${Math.round(dayPace * 100)}% of the working day (${WORK_FROM}:00-${WORK_TO}:00) gone`,
  }, {
    name: 'Month',
    label: 'Month',
    used: m.used / m.limit,
    ticks: [{ at: pace, red: ahead }],
    pace,
    ahead,
    // Used, then the pace, as the usage windows show it (owner, 2026-10-27).
    value: `${Math.round(m.used / m.limit * 100)}% / ${Math.round(pace * 100)}%`,
    detail: `${dollars(m.used)} of ${dollars(m.limit)}`,
    alt: `pace ${Math.round(pace * 100)}%${ahead ? ', ahead of pace' : ''}`,
    tip: `${cents(m.used)} of ${cents(m.limit)}${unit} this month (as of ${asOf})`
      + ` · second figure and arrow: ${Math.round(pace * 100)}% of the month gone · `
      + (ahead ? 'ahead of pace: at this rate the limit runs out before the month ends' : 'left of it, the limit lasts the month'),
  }]
}

const CACHE_WARN = 10 * 60_000

const GREEN = '#2e9e6a'
export const RED = '#d9534f'
// The fill's colour says how full the bar is wherever it ends (design pick A5, owner 2026-10-03).
const HEAT: [number, string][] = [[0, GREEN], [0.45, '#8cc152'], [0.7, '#e0b02a'], [1, RED]]
// The bar sits in the middle of an image of height H, so it lines up with the text beside it; the
// arrows take the band above it. Widths are kept small enough for one row (owner, 2026-10-03).
// The limit bars went from 64 to 58 px to give the figures room, then to 112, the 5-hour bar too,
// with the room the Context ring gave back (owner, 2026-10-27).
const W = 112, H = 18, BAR = 8, BAR_Y = (H - BAR) / 2
// A side panel narrows the band (107 to 86 cells with the browser open, owner's probe, 2026-10-27),
// so the bars share what the rest leaves, between MIN_W and W; below that the band wraps. A tree
// cannot measure its text, so the rest is counted in cells, labels by their letters, plus SLACK for what
// the count misses: at 4 the bars still wrapped at 86 cells (owner, 2026-10-27), and 112 px fit at 107.
const MIN_W = 24, CELL_PX = 10, SLACK = 18
// Each figure's box holds its widest value - `~100%`, ` /100%` (caption size), `expired` - judged by
// eye, since a tree cannot measure its text. A Box's width counts character cells, not pixels: the
// first try in pixels made each meter a whole row wide, and 5/4/7 cells left wide gaps (owner's
// screenshots, 2026-10-27): a desktop cell is about 10 px. Three cells for the pace wrapped it under
// the figure as soon as the used share reached two digits (`10% / 53%`, owner, 2026-10-27).
const USED_W = 4
const PACE_W = 5
const CACHE_W = 5
// How long the first draw waits for the figures before drawing the band without them.
const FIRST_WAIT = 150

const isCollapsed = atom({ plugin: 'asdev', key: 'isCollapsed' } as const, false)
// Set by compaction.ts while a main-chat compaction runs.
const compactingSince = atom({ plugin: 'asdev', key: 'compactingSince' } as const, 0)
// Set by compaction.ts at each main-thread reply: the moment the prompt cache was last refreshed.
const cacheAt = atom({ plugin: 'asdev', key: 'cacheAt' } as const, 0)

const k = (n: number) => `${Math.round(n / 1000)}k`

// The collapsed bars' hover tooltip. It shows only in an isInteractive Svg, so that one is sized; the
// transparent rect lets the gaps around the bars catch the pointer too.
const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
const tipped = (tip: string, w: number, h: number, body: string) =>
  `<g><title>${esc(tip)}</title><rect width="${w}" height="${h}" fill="transparent"/>${body}</g>`

// One bar: `used` and the ticks are fractions of the whole (0..1); a tick is an arrow above it and a
// line down through it (owner, 2026-10-04).
function bar(width: number, used: number, ticks: { at: number; faint?: boolean; red?: boolean }[]): string {
  const x = (f: number) => Math.min(width, Math.max(0, f * width))
  const stops = HEAT.map(([at, c]) => `<stop offset="${at}" stop-color="${c}"/>`).join('')
  const arrows = ticks
    .filter(t => t.at > 0 && t.at < 1)
    .map(t => {
      const fill = t.red ? RED : t.faint ? '#8888' : '#888'
      return `<polygon points="${x(t.at) - 4},0 ${x(t.at) + 4},0 ${x(t.at)},5" fill="${fill}"/>`
        + `<rect x="${x(t.at) - 0.75}" y="4" width="1.5" height="${BAR_Y + BAR - 4}" fill="${fill}"/>`
    })
    .join('')
  // The fill is clipped to the track's rounded shape: drawn rounded itself, a fill only a few pixels
  // wide came out square at the left end (owner's screenshot, 2026-10-04).
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${H}" viewBox="0 0 ${width} ${H}">`
    + `<defs><linearGradient id="heat" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="${width}" y2="0">${stops}</linearGradient>`
    + `<clipPath id="track"><rect y="${BAR_Y}" width="${width}" height="${BAR}" rx="4"/></clipPath></defs>`
    + `<rect y="${BAR_Y}" width="${width}" height="${BAR}" rx="4" fill="#8884"/>`
    + `<rect y="${BAR_Y}" width="${x(used)}" height="${BAR}" clip-path="url(#track)" fill="url(#heat)"/>` + arrows
    + '</svg>'
}

// The cache ring empties as the cache runs out: `left` is the fraction of its life still to run.
function ring(left: number, colour: string): string {
  const c = 2 * Math.PI * 7
  return '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18">'
    + '<circle cx="9" cy="9" r="7" fill="none" stroke="#8884" stroke-width="3"/>'
    + `<circle cx="9" cy="9" r="7" fill="none" stroke="${colour}" stroke-width="3" stroke-dasharray="${(c * left).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 9 9)"/>`
    + '</svg>'
}

// The Context ring, the cache ring's size, in sections split at `cuts`: the gaps between them are the
// marks, which stay visible at 18 px where ticks on so small a shape would not (owner's pick, 2026-10-27).
// The fill takes the colour of the section it has reached.
function sections(used: number, cuts: number[]): string {
  const c = 2 * Math.PI * 7, gap = 1.4
  const ends = [0, ...cuts.filter(f => f > 0 && f < 1), 1]
  const at = ends.slice(1).findIndex(f => used < f)
  const fill = [GREEN, '#e0b02a', RED][Math.min(2, at < 0 ? ends.length - 2 : at)]
  const arc = (from: number, to: number, colour: string) => (to - from) * c > gap
    ? `<circle cx="9" cy="9" r="7" stroke="${colour}" stroke-dasharray="${((to - from) * c - gap).toFixed(2)} ${c.toFixed(2)}" stroke-dashoffset="${(-(from * c + gap / 2)).toFixed(2)}"/>` : ''
  const parts = ends.slice(1).map((to, i) => arc(ends[i], to, ['#8884', '#e0b02a55', '#d9534f55'][Math.min(2, i)])
    + arc(ends[i], Math.min(to, used), fill)).join('')
  return '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18">'
    + `<g transform="rotate(-90 9 9)" fill="none" stroke-width="3">${parts}</g></svg>`
}

// The collapsed band: a thin bar per fraction, the first on top; a single one sits in the middle.
function mini(fractions: number[], tip: string): string {
  const stops = HEAT.map(([at, c]) => `<stop offset="${at}" stop-color="${c}"/>`).join('')
  const row = (y: number, f: number) => `<rect y="${y}" width="28" height="3" rx="1.5" fill="#8884"/>`
    + `<rect y="${y}" width="${(28 * Math.min(1, Math.max(0, f))).toFixed(1)}" height="3" rx="1.5" fill="url(#heat)"/>`
  const ys = fractions.length === 1 ? [3.5] : [1, 6]
  return '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="10" viewBox="0 0 28 10">'
    + `<defs><linearGradient id="heat" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="28" y2="0">${stops}</linearGradient></defs>`
    + tipped(tip, 28, 10, fractions.map((f, i) => row(ys[i], f)).join('')) + '</svg>'
}

// Clawd, the Claude Code mascot, as pixels (X body, E eye), for the desktop's animated drawings:
// idle tricks at random now and then, and the vacuum during a compaction (owner, 2026-10-04).
// They run as SMIL; the terminal cannot animate one, so it gets neither. A trick needs no
// isInteractive frame, so it is drawn as an image.
const CLAWD = ['..XXXXXXXX..', '..XXXXXXXX..', '..XEXXXXEX..', 'XXXXXXXXXXXX', 'XXXXXXXXXXXX', '..XXXXXXXX..', '..X.X..X.X..', '..X.X..X.X..']
const ORANGE = '#d97757'

function clawd(extra = ''): string {
  const px = 2
  const cells = (rows: number[]) => CLAWD.flatMap((row, y) => rows.includes(y)
    ? [...row].map((c, x) => c === '.' ? '' : `<rect x="${x * px}" y="${y * px}" width="${px}" height="${px}" fill="${c === 'E' ? '#1f1e1c' : ORANGE}"/>`)
    : []).join('')
  return `<g>${cells([0, 1, 2, 3, 4, 5])}<g>${cells([6, 7])}`
    + '<animateTransform attributeName="transform" type="translate" values="0 0;0 -1;0 0" dur="0.3s" repeatCount="indefinite"/></g>'
    + extra + '</g>'
}

// The stage lies over the band's first row; positions along it follow the desktop layout roughly
// (context bar near 60–150 px, the week bar near 380–470, the cache ring near 540).
const STAGE_W = 620, STAGE_H = 24
const stage = (body: string) => `<svg xmlns="http://www.w3.org/2000/svg" width="${STAGE_W}" height="${STAGE_H}" viewBox="0 0 ${STAGE_W} ${STAGE_H}" shape-rendering="crispEdges">${body}</svg>`
const move = (values: string, keyTimes: string, dur: number) =>
  `<animateTransform attributeName="transform" type="translate" values="${values}" keyTimes="${keyTimes}" dur="${dur}ms" fill="freeze"/>`

export const TRICKS: Record<string, { ms: number; alt: string; svg: () => string }> = {
  // Pops up behind the context bar, waves and ducks back down.
  peek: {
    ms: 6000,
    alt: 'Clawd peeks up behind the context bar and waves',
    svg: () => stage(`<g transform="translate(100 ${STAGE_H})">${move(`100 ${STAGE_H};100 ${STAGE_H};100 6;100 6;100 ${STAGE_H};100 ${STAGE_H}`, '0;0.1;0.25;0.75;0.9;1', 6000)}`
      + `<g>${clawd()}<animateTransform attributeName="transform" type="rotate" values="0 12 8;-8 12 8;8 12 8;-8 12 8;8 12 8;0 12 8" keyTimes="0;0.3;0.4;0.5;0.6;0.7" dur="6000ms" fill="freeze"/></g></g>`),
  },
  // Strolls in along the bar, dozes on the week meter, then fades.
  stroll: {
    ms: 12000,
    alt: 'Clawd strolls along the bar and naps on the week meter',
    svg: () => stage(`<g transform="translate(-30 6)">${move('-30 6;400 6;400 6', '0;0.45;1', 12000)}${clawd()}`
      + '<animate attributeName="opacity" values="1;1;0" keyTimes="0;0.85;1" dur="12000ms" fill="freeze"/></g>'
      + '<text x="428" y="9" font-size="9" font-weight="700" fill="#888" opacity="0">z z<animate attributeName="opacity" values="0;0;1;1;0" keyTimes="0;0.5;0.58;0.8;0.86" dur="12000ms" fill="freeze"/></text>'),
  },
  // Hops across the meters like platforms and lands on the cache ring.
  hop: {
    ms: 8000,
    alt: 'Clawd hops across the meters onto the cache ring',
    svg: () => stage(`<g transform="translate(40 7)">${move('40 7;90 0;140 7;200 0;260 7;320 0;380 7;440 0;500 7;540 7;540 7', '0;0.08;0.16;0.24;0.32;0.4;0.48;0.56;0.64;0.7;1', 8000)}${clawd()}`
      + '<animate attributeName="opacity" values="1;1;0" keyTimes="0;0.88;1" dur="8000ms" fill="freeze"/></g>'),
  },
  // Dances between the meters, swaying and bobbing, with notes rising (owner asked for more, 2026-10-04).
  dance: {
    ms: 7000,
    alt: 'Clawd dances between the meters',
    svg: () => stage('<g transform="translate(300 8)" opacity="0"><animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.08;0.9;1" dur="7000ms" fill="freeze"/>'
      + '<g><animateTransform attributeName="transform" type="translate" values="0 0;0 -3;0 0" dur="0.5s" repeatCount="indefinite"/>'
      + `<g>${clawd()}<animateTransform attributeName="transform" type="rotate" values="-10 12 16;10 12 16;-10 12 16" dur="1s" repeatCount="indefinite"/></g></g>`
      + [[28, 0], [34, 0.5], [-8, 1]].map(([x, d]) => `<text x="${x}" y="8" font-size="9" font-weight="700" fill="${ORANGE}" opacity="0">♪`
        + `<animate attributeName="y" values="8;-6" dur="1.5s" begin="${d}s" repeatCount="indefinite"/>`
        + `<animate attributeName="opacity" values="1;0" dur="1.5s" begin="${d}s" repeatCount="indefinite"/></text>`).join('')
      + '</g>'),
  },
  // Juggles three bits of context, one in each meter colour.
  juggle: {
    ms: 7000,
    alt: 'Clawd juggles three bits of context',
    svg: () => stage('<g transform="translate(250 8)" opacity="0"><animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.08;0.9;1" dur="7000ms" fill="freeze"/>'
      + clawd()
      + ['#3fa66b', '#e2a33a', ORANGE].map((c, i) => `<rect x="-1.5" y="-1.5" width="3" height="3" fill="${c}">`
        + `<animateMotion path="M 1 6 Q 12 -12 23 6 Q 12 -12 1 6" dur="1.2s" begin="${i * 0.4}s" repeatCount="indefinite"/></rect>`).join('')
      + '</g>'),
  },
  // Runs across the band and does a backflip halfway.
  flip: {
    ms: 6000,
    alt: 'Clawd runs across the band and does a backflip',
    svg: () => stage(`<g transform="translate(-30 8)">${move('-30 8;650 8', '0;1', 6000)}`
      + `<g>${move('0 0;0 0;0 -6;0 0;0 0', '0;0.42;0.5;0.58;1', 6000)}`
      + `<g>${clawd()}<animateTransform attributeName="transform" type="rotate" values="0 12 8;0 12 8;-360 12 8;-360 12 8" keyTimes="0;0.42;0.58;1" dur="6000ms" fill="freeze"/></g></g></g>`),
  },
  // Chases a bug that zigzags across the band.
  chase: {
    ms: 7000,
    alt: 'Clawd chases a bug across the band',
    svg: () => stage(`<g transform="translate(-10 14)">${move('-10 14;150 9;250 16;380 9;500 15;640 11', '0;0.2;0.4;0.6;0.8;1', 5000)}`
      + '<rect width="4" height="3" fill="#2f2f2d"/><rect x="-1" y="3" width="1" height="1" fill="#2f2f2d"/><rect x="4" y="3" width="1" height="1" fill="#2f2f2d"/></g>'
      + `<g transform="translate(-40 8)"><animateTransform attributeName="transform" type="translate" values="-40 8;120 8;220 8;350 8;470 8;640 8" keyTimes="0;0.2;0.4;0.6;0.8;1" dur="5200ms" begin="1s" fill="freeze"/>${clawd()}</g>`),
  },
}

// Compaction: the meters empty into Clawd's vacuum, bits of context streaming down the hose.
const VACUUM = '<g transform="translate(-22 0)"><rect x="0" y="4" width="16" height="10" rx="3" fill="#6b6a66"/>'
  + '<rect x="-10" y="10" width="12" height="3" fill="#6b6a66"/><circle cx="4" cy="15" r="2" fill="#2f2f2d"/><circle cx="13" cy="15" r="2" fill="#2f2f2d"/></g>'
function vacuum(): string {
  const stops = HEAT.map(([at, c]) => `<stop offset="${at}" stop-color="${c}"/>`).join('')
  const bits = [[20, 9, 0], [70, 14, 0.3], [120, 10, 0.6], [170, 15, 0.9], [210, 11, 0.45]]
    .map(([x, y, d]) => `<rect x="${x}" y="${y}" width="4" height="4" rx="1" fill="${ORANGE}" opacity="0">`
      + `<animate attributeName="x" from="${x}" to="236" dur="1.2s" begin="${d}s" repeatCount="indefinite"/>`
      + `<animate attributeName="opacity" values="1;0" dur="1.2s" begin="${d}s" repeatCount="indefinite"/></rect>`).join('')
  return `<svg xmlns="http://www.w3.org/2000/svg" width="300" height="${STAGE_H}" viewBox="0 0 300 ${STAGE_H}" shape-rendering="crispEdges">`
    + `<defs><linearGradient id="heat" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="220" y2="0">${stops}</linearGradient></defs>`
    + '<rect y="8" width="220" height="8" rx="4" fill="#8884"/>'
    + '<rect y="8" width="220" height="8" rx="4" fill="url(#heat)"><animate attributeName="width" values="220;0" dur="3s" repeatCount="indefinite"/></rect>'
    + bits
    + `<g transform="translate(266 4)">${clawd(VACUUM)}<animateTransform attributeName="transform" type="translate" values="266 4;267 3" dur="0.12s" repeatCount="indefinite"/></g>`
    + '</svg>'
}

function blocks(used: number, pace?: number, cells = 20): string {
  const filled = Math.min(cells, Math.round(used * cells))
  const cell = (i: number) => (pace !== undefined && i === Math.round(pace * cells) ? '│' : i < filled ? '█' : '░')
  return Array.from({ length: cells }, (_, i) => cell(i)).join('')
}

type Row = { name: string; label: string; used: number; ticks: { at: number; faint?: boolean; red?: boolean }[]; pace?: number; value: string; detail: string; alt: string; tip: string; old?: boolean; ahead?: boolean; round?: boolean }

// Module-level on purpose: a reload cancels the old timer and starts this over with it.
let ticking = false
// Whether the figures have answered once; until then a draw does not wait on them (see FIRST_WAIT).
let answered = false
// The trick on stage and when the next one may start: the first within a few minutes, then one
// every 12 to 25 minutes, so Clawd stays a surprise.
let trick: { name: string; until: number } | undefined
let nextTrickAt = 0
let lastTrick = ''
const between = (lo: number, hi: number) => (lo + Math.random() * (hi - lo)) * 60_000

export const register: Register = on => {
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    // Shown even collapsed: the app gives no sign of a compaction it did not start (traps.md, Mods).
    const since = await read($, compactingSince)
    if (since && !e.props.hasSurvey) {
      const { Text } = $.ui.resolve(e)
      const s = Math.round(((await $.clock.now()) - since) / 1000)
      const text = <Text>Compacting… {s} s (about a minute; messages wait)</Text>
      if (e.surface === 'terminal') {
        return text
      }
      // The drawing never changes while the seconds do, so the redraw each second leaves it playing.
      // An interactive Svg is a frame that falls back to 150 px high without a size (owner, 2026-10-04).
      const { Box, Svg } = $.ui.resolve(e)
      return (
        <Box flexDirection="row" alignItems="center" gap={1}>
          <Svg source={vacuum()} alt="Clawd vacuums up the old context" width={300} height={STAGE_H} isInteractive />
          {text}
        </Box>
      )
    }
    if (e.props.hasSurvey || (await read($, isCollapsed))) {
      return next(e)
    }

    // The first answer can take seconds after the app starts, so the band is drawn without the
    // figures and drawn again once they come (owner, 2026-10-03).
    const figures = Promise.all([
      $.session.usage(),
      // Unreadable settings: the model's window still gives a usable bar.
      ($.settings.read() as Promise<{ autoCompactWindow?: number }>).catch(() => ({}) as { autoCompactWindow?: number }),
      $.store.get('limits') as Promise<SessionRateLimit[] | undefined>,
      $.store.get('month'),
      $.store.get('dayStart'),
      $.store.get('limitsAt'),
    ])
    const got = answered ? await figures : await Promise.race([figures, $.clock.sleep(FIRST_WAIT).then(() => undefined)])
    if (got) {
      answered = true
    } else {
      void figures.then(() => { answered = true; $.ui.invalidate('ui.render') })
    }
    const [usage, settings, kept, keptMonth, keptDay, keptAt] = got ?? []
    const context = usage?.context
    const cost = usage?.cost
    // Absent in a fresh session and after a compaction or relaunch until the next reply; the band
    // stays up rather than vanishing (it hid itself whole here before, 2026-10-02).
    const tokens = context?.tokens
    // Until then the local estimate /context and the app's rail show fills the gap, drawn as one
    // (owner, 2026-10-27). Asked only in the gap: the plain call is free, this one counts.
    const estimate = context && tokens === undefined
      ? (await $.session.usage({ breakdown: 'summary' }).catch(() => undefined))?.context.breakdown?.totalTokens
      : undefined
    const fill = tokens ?? estimate
    const now = await $.clock.now()
    // The kept figures win over this session's own: a chat left idle keeps the reading of its last
    // reply, hours behind (owner, 2026-10-04). Until the session's first reply they are drawn faint,
    // unless a reply or usage read elsewhere kept them a few minutes ago.
    const own = usage?.rateLimits ?? []
    const old = !own.length && !(num(keptAt) && Math.abs(now - keptAt) < LIMITS_FRESH)
    const months = monthRows(asMonth(keptMonth), asDay(keptDay), now)
    // The account figure is the month's own: a monthly window beside it would count it twice.
    const rateLimits = pickLimits(own, kept ?? [], own.length > 0 || tokens !== undefined, now)
      .filter(r => !months.length || !isMonthly(r.kind))

    // The window the session compacts against is the setting when one is set, not the model's.
    const setting = settings?.autoCompactWindow
    const limit = context ? Math.min(context.window, setting ?? context.window) : 0
    const compactAt = limit - COMPACT_MARGIN
    const usd = cost ? `$${cost.usd.toFixed(2)}` : ''

    // A percentage keeps the band on one row; the tokens are in the hover card (owner, 2026-10-05).
    const shown = !limit ? '…' : fill === undefined ? '–' : `${tokens === undefined ? '~' : ''}${Math.round(fill / limit * 100)}%`
    const list: Row[] = [{
      name: 'Context',
      label: 'Context',
      // A ring split where it compacts, in place of the label and bar (owner's pick, 2026-10-27).
      round: true,
      used: limit ? (fill ?? 0) / limit : 0,
      ticks: limit ? [{ at: TRIGGER_FROM / limit, faint: true }, { at: compactAt / limit }] : [],
      value: shown,
      // Kept short: a long line wraps the band onto an extra row (owner, 2026-10-02). The ticks show
      // where the mod first asks for a compaction and where the engine compacts; the alt text names them.
      detail: shown + (usd ? ` · ${usd}` : ''),
      alt: limit ? `compacts at a checkpoint from ${k(TRIGGER_FROM)}, by itself ~${k(compactAt)}` : 'loading',
      tip: !limit ? 'Waiting for the first reply'
        : `${fill === undefined ? 'Unknown until the next reply'
          : `${tokens === undefined ? '~' : ''}${k(fill)} of ${k(limit)} tokens used${tokens === undefined ? ' (estimated until the next reply)' : ''}`}`
          + ` · first gap ${k(TRIGGER_FROM)}: compacts at the next planned checkpoint · second gap ~${k(compactAt)}: compacts by itself`,
      old: !limit,
    }, ...months]

    // The pace arrow is the share of the window already elapsed: staying left of it means the
    // limit lasts until it resets.
    for (const r of rateLimits) {
      const resets = r.resetsAt ? Date.parse(r.resetsAt) : NaN
      const span = windowMs(r.kind, resets)
      const pace = span && !Number.isNaN(resets)
        ? Math.min(1, Math.max(0, 1 - (resets - now) / span))
        : undefined
      // A figure from a window that has since reset says nothing about the new one.
      const gone = resets <= now
      const used = gone ? 0 : r.percentUsed / 100
      const ahead = pace !== undefined && used > pace
      const h = Math.max(0, Math.round((resets - now) / 3600_000))
      const when = Number.isNaN(resets) ? '' : h < 48 ? `${h}h` : `${Math.round(h / 24)}d`
      list.push({
        name: limitName(r.kind),
        label: limitLabel(r.kind),
        used,
        // Past the pace line the arrow and the figure turn red (owner, 2026-10-04).
        ticks: pace === undefined ? [] : [{ at: pace, red: ahead }],
        ahead,
        pace,
        // Used, then the pace: how much it may have used by now and still last (owner, 2026-10-04).
        // The reset time moves to the hover strip.
        value: gone ? '–' : `${r.percentUsed}%` + (pace === undefined ? '' : ` / ${Math.round(pace * 100)}%`),
        detail: gone ? '–' : `${r.percentUsed}%` + (pace === undefined ? '' : ` / ${Math.round(pace * 100)}%`),
        old,
        alt: (when ? `resets in ${when}` : '') + (pace === undefined ? '' : `, pace ${Math.round(pace * 100)}%${ahead ? ', ahead of pace' : ''}`),
        tip: `${gone ? 'Reset since the last figure' : `${r.percentUsed}% used`}${when ? `, resets in ${when}` : ''}`
          + (old && !gone ? ' (last known)' : '')
          + (pace === undefined ? '' : ` · second figure and arrow: ${Math.round(pace * 100)}% of the window gone · `
            + (ahead ? 'ahead of pace: at this rate it runs out before the reset' : 'left of it, it lasts until the reset')),
      })
    }
    // Nothing to stand in yet: the rows still show, waiting.
    if (!got && !rateLimits.length) {
      for (const kind of ['five_hour', 'seven_day']) {
        list.push({ name: LIMIT_NAME[kind], label: LIMIT_LABEL[kind], used: 0, ticks: [], value: '…', detail: '…', alt: 'loading', tip: 'Waiting for the first figure', old: true })
      }
    }

    // None before the first reply: there is no cache to time yet. After a restart the session state is
    // empty, and the time this chat's last reply was kept under its id stands in.
    const stored = (await read($, cacheAt))
      || asTimes(await $.store.get(CACHE_STORE))[await $.session.id().catch(() => '')]
    const at = num(stored) ? stored : 0
    // The countdown and Clawd's tricks move with no new figures, so the band redraws itself each
    // minute. Started here rather than at session start, which a hot reload does not repeat.
    if (!ticking) {
      ticking = true
      $.clock.every(60_000, async () => {
        $.ui.invalidate('ui.render')
        // Only after some session has read once: one without the login would otherwise ask every minute.
        if (num(await $.store.get('monthTry'))) await refreshMonth($, await $.clock.now(), USAGE_IDLE).catch(() => {})
      })
    }
    const left = at ? at + CACHE_TTL - now : 0
    const cache = at && {
      text: left > 0 ? `${Math.ceil(left / 60_000)}m` : 'expired',
      colour: left > CACHE_WARN ? GREEN : RED,
      left: Math.max(0, left) / CACHE_TTL,
    }

    const collapse = () => update($, isCollapsed, () => true)

    if (e.surface === 'terminal') {
      const { Box, Button, Text } = $.ui.resolve(e)
      return (
        <Box flexDirection="column">
          {list.map((r, i) => (
            <Box key={r.name} flexDirection="row" gap={1}>
              <Text dimColor>{r.name.padEnd(7)} {blocks(r.used, r.pace)}</Text>
              {r.ahead ? <Text color={RED}>{r.detail}</Text> : <Text dimColor>{r.detail}</Text>}
              {i === 0 && cache ? <Text key="cache" color={cache.colour}>· cache {cache.text}</Text> : null}              {i === 0 ? <Button key="hide" label="x" plain onPress={collapse} /> : null}
            </Box>
          ))}
        </Box>
      )
    }

    // Each start and end wakes the band at its moment rather than at the next minute's redraw.
    const wake = (at: number) => void $.clock.sleep(at - now).then(() => $.ui.invalidate('ui.render'), () => {})
    if (!nextTrickAt) {
      nextTrickAt = now + between(2, 6)
      wake(nextTrickAt)
    }
    if (trick && now >= trick.until) {
      trick = undefined
    }
    if (!trick && now >= nextTrickAt) {
      // Never the same trick twice running, so the variety shows.
      const names = Object.keys(TRICKS).filter(n => n !== lastTrick)
      const name = lastTrick = names[Math.floor(Math.random() * names.length)]
      trick = { name, until: now + TRICKS[name].ms }
      nextTrickAt = trick.until + between(12, 25)
      wake(trick.until)
      wake(nextTrickAt)
    }
    const shownTrick = trick && TRICKS[trick.name]

    const { Box, Button, Svg, Text } = $.ui.resolve(e)
    const bars = list.filter(r => !r.round).length
    const cols = e.viewport?.columns
    const meters = list.reduce((n, r) => n + (r.round ? 2 : r.label.length + 1) + 1 + USED_W + (r.value.includes(' / ') ? PACE_W : 0), 0)
    const rest = (cost: boolean, ring: boolean) => meters + (ring ? 3 + CACHE_W : 0) + (cost ? usd.length + 1 : 0) + 2
      + (list.length + (ring ? 1 : 0)) * 2 + SLACK
    const fits = (n: number) => !cols || cols - n >= bars * MIN_W / CELL_PX
    // Once the bars are at their narrowest, the cost goes first, then the cache ring (owner, 2026-10-27).
    const showCost = !!usd && fits(rest(true, !!cache))
    const showCache = !!cache && fits(rest(showCost, true))
    const barW = !cols || !bars ? W
      : Math.max(MIN_W, Math.min(W, Math.floor((cols - rest(showCost, showCache)) * CELL_PX / bars)))
    const meter = (r: Row) => {
      // The pace sits raised, smaller and grey after the figure, so the used share reads first
      // (owner, 2026-10-27). No Text draws superscript: a top-aligned smaller run stands in for it.
      // A fixed width, so a figure that gains a digit no longer shifts the meters after it (owner, 2026-10-27).
      const [used, pace] = r.value.split(' / ')
      const alt = `${r.name}: ${r.value}${r.old && r.alt !== 'loading' ? ' (last known)' : ''}${r.alt ? `, ${r.alt}` : ''}`
      return [
        ...r.round
          ? [<Svg key="bar" source={sections(r.used, r.ticks.map(t => t.at))} alt={alt} width={18} height={18} />]
          : [<Text key="label" dimColor>{r.label}</Text>, <Svg key="bar" source={bar(barW, r.used, r.ticks)} alt={alt} width={barW} height={H} />],
        <Box key="value" flexDirection="row" alignItems="flex-start" width={USED_W + (pace ? PACE_W : 0)}>
          {r.old ? <Text tabular dimColor>{used}</Text> : <Text tabular bold color={r.ahead ? RED : undefined}>{used}</Text>}
          {/* Caption is the smallest size there is, so the pace is made bolder instead (owner, 2026-10-27). */}
          {pace ? <Text size="caption" weight="semibold" tabular dimColor>{` / ${pace}`}</Text> : null}
        </Box>,
      ]
    }
    const cacheMeter = cache && (() => [
      <Svg key="ring" source={ring(cache.left, cache.colour)} alt={`Prompt cache: ${cache.text}${left > 0 ? ' left' : ''}`} width={18} height={18} />,
      <Box key="value" width={CACHE_W}><Text tabular bold color={cache.colour}>{cache.text}</Text></Box>,
    ])
    // Hovering a meter opens a card saying what it means, one point per line. The desktop draws it
    // as its own light card above the band, so it keeps the card's colours (the dark strip planned
    // over the band came out white on white, 2026-10-04). It sits unkeyed inside the meter's keyed
    // Box: a keyed Box drawn hidden scopes its own hover, which the pointer can never reach.
    const card = (title: string, text: string, fromRight?: boolean) => (
      <Box position="absolute" top={0} {...(fromRight ? { right: 0 } : { left: 0 })} display="none"
        hover={{ display: 'flex' }} flexDirection="column" paddingX={1}>
        <Text bold>{title}</Text>
        {/* The figure first, then the explanation dimmed. */}
        {text.split(' · ').map((line, i) => (
          <Text key={String(i)} wrap="wrap" dimColor={i > 0}>{line.charAt(0).toUpperCase() + line.slice(1)}</Text>
        ))}
      </Box>
    )
    return (
      <Box key="band" flexDirection="row" flexWrap="wrap" alignItems="center" columnGap={2} rowGap={1}>
        {list.map(r => (
          <Box key={r.name} flexDirection="row" alignItems="center" gap={1}>
            {meter(r)}
            {card(r.name, r.tip)}
          </Box>
        ))}
        {cacheMeter && showCache ? (
          // Last in the row, so its card grows leftwards rather than off the band's edge.
          <Box key="cache" flexDirection="row" alignItems="center" gap={1}>
            {cacheMeter()}
            {card('Prompt cache', left > 0
              ? `${cache.text} left · each reply renews it; once it expires, the next reply re-reads the whole context at full price`
              : 'The next reply re-reads the whole context at full price, then the cache runs for an hour again', true)}
          </Box>
        ) : null}
        <Box key="end" flexDirection="row" alignItems="center" gap={1} flexGrow={1} justifyContent="flex-end">
          {showCost ? <Text tabular bold>{usd}</Text> : null}
          <Button key="hide" label="✕" role="dismiss" plain dimColor onPress={collapse} />
        </Box>
        {/* Over the meters without moving them; the drawing stays the same for the whole trick. Any
            drawing there catches the pointer, so while it is on the band Clawd steps out of view: the
            outer Box has no key, so its hover follows the band's, not the drawing's own. */}
        {shownTrick ? (
          <Box position="absolute" top={0} left={0} hover={{ top: -10 * STAGE_H }}><Box key="clawd">
            <Svg source={shownTrick.svg()} alt={shownTrick.alt} width={STAGE_W} height={STAGE_H} />
          </Box></Box>
        ) : null}
      </Box>
    )
  })

  // New figures redraw the band at once, not at the app's next unrelated redraw.
  on('session.measure', async ($, e, next) => {
    $.ui.invalidate('ui.render')
    // Not awaited: the measure never waits on the network.
    void refreshMonth($, await $.clock.now()).catch(() => {})
    // Kept for the next session's first draw, before its own first reply. An empty list is kept too, so
    // windows the account no longer has stop standing in. A session that never had a window does not
    // name `rateLimits` as changed, so a reply with none clears the kept ones as well.
    // Dated, so a usage read asked before this reply does not overwrite it.
    if (e.changed.includes('rateLimits')) {
      await $.store.set('limits', e.rateLimits)
      await $.store.set('limitsAt', await $.clock.now())
    } else if (!e.rateLimits.length && e.context.tokens !== undefined
      && ((await $.store.get('limits')) as SessionRateLimit[] | undefined)?.length) {
      await $.store.set('limits', [])
      await $.store.set('limitsAt', await $.clock.now())
    }
    // Which kinds arrive and when last, to check the labels and pace against after the move to Enterprise.
    if (e.changed.includes('rateLimits') && e.rateLimits.length) {
      const at = new Date(await $.clock.now()).toISOString()
      const seen = ((await $.store.get('kindsSeen')) ?? {}) as Record<string, string>
      await $.store.set('kindsSeen', { ...seen, ...Object.fromEntries(e.rateLimits.map(r => [r.kind, at])) })
    }
    return next(e)
  })

  // Collapsed, the band becomes one button in the footer below the prompt.
  on('ui.render', { component: 'SessionMode' }, async ($, e, next) => {
    if (!(await read($, isCollapsed))) {
      return next(e)
    }
    // A small bar per limit, the first two the band shows, in place of a word (owner, 2026-10-03);
    // Today and Month while the account figure shows.
    const got = await Promise.race([
      Promise.all([$.session.usage(), $.store.get('limits') as Promise<SessionRateLimit[] | undefined>, $.store.get('month'), $.store.get('dayStart')]),
      $.clock.sleep(FIRST_WAIT).then(() => undefined),
    ])
    const now = await $.clock.now()
    const own = got?.[0].rateLimits ?? []
    const months = monthRows(asMonth(got?.[2]), asDay(got?.[3]), now).map(r => ({ name: r.name, used: r.used }))
    // Usage windows first: on a plan that has them they bind sooner than the spend (Enterprise has none).
    const rows = [...pickLimits(own, got?.[1] ?? [], own.length > 0 || got?.[0].context.tokens !== undefined, now)
      .filter(r => !months.length || !isMonthly(r.kind))
      // A figure from a window that has since reset says nothing about the new one.
      .map(r => ({ name: limitName(r.kind), used: hasReset(r, now) ? 0 : r.percentUsed / 100 })), ...months]
      .slice(0, 2)
    const pct = (f: number) => `${Math.round(f * 100)}%`
    const show = () => update($, isCollapsed, () => false)
    const { Box, Button, Text } = $.ui.resolve(e)
    const modes = e.props.modes.length ? <Text dimColor>{e.props.modes.join(' & ')}</Text> : null
    if (e.surface === 'terminal') {
      return (
        <Box flexDirection="row" gap={1}>
          {modes}
          <Button key="show" label={rows.map(r => blocks(r.used, undefined, 4)).join(' ') || '▴'} plain onPress={show} />
        </Box>
      )
    }
    // A desktop Button holds only a label, so the bars are drawn beside a one-glyph button that opens the band.
    const { Svg } = $.ui.resolve(e)
    const where = rows.length > 1 ? [' (top)', ' (bottom)'] : ['']
    return (
      <Box flexDirection="row" alignItems="center" gap={1}>
        {modes}
        {rows.length ? (
          <Svg source={mini(rows.map(r => r.used), rows.map((r, i) => `${r.name}: ${pct(r.used)} used${where[i]}`).join('\n'))}
            alt={rows.map((r, i) => `${i ? r.name.toLowerCase() : r.name} ${pct(r.used)}`).join(', ')} width={28} height={10} isInteractive />
        ) : null}
        <Button key="show" label="▴" plain dimColor onPress={show} />
      </Box>
    )
  })
}
