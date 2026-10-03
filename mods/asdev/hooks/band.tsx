import { atom, read, update } from 'claude-code'
import type { Register, SessionRateLimit } from 'claude-code'

// Compaction lands about 33k below the window (measured 2026-10-01, main chats and agents alike).
const COMPACT_MARGIN = 33_000
// Past this a session should compact at its next clean break (roadmap: graceful compaction).
const TIDY_AT = 200_000
const WINDOW_MS: Record<string, number> = { five_hour: 5 * 3600_000, seven_day: 7 * 86400_000 }
const LIMIT_NAME: Record<string, string> = { five_hour: '5 hours', seven_day: 'Week' }
const LIMIT_LABEL: Record<string, string> = { five_hour: '5h', seven_day: 'Week' }
const LIMIT_WIDTH: Record<string, number> = { five_hour: 48 }

// The main chat's prompt cache lasts an hour from the last reply (the 1-hour TTL; a session in usage
// overage drops to 5 minutes, which the engine does not report). Past it, the next message writes the
// whole context to the cache again at the full write price.
const CACHE_TTL = 3600_000
const CACHE_WARN = 10 * 60_000

const GREEN = '#2e9e6a', RED = '#d9534f'
// The fill's colour says how full the bar is wherever it ends (design pick A5, owner 2026-10-03).
const HEAT: [number, string][] = [[0, GREEN], [0.45, '#8cc152'], [0.7, '#e0b02a'], [1, RED]]
// The bar sits in the middle of an image of height H, so it lines up with the text beside it; the
// arrows take the band above it. Widths are kept small enough for one row (owner, 2026-10-03).
const W = 88, H = 18, BAR = 8, BAR_Y = (H - BAR) / 2
// How long the first draw waits for the figures before drawing the band without them.
const FIRST_WAIT = 150

const isCollapsed = atom({ plugin: 'asdev', key: 'isCollapsed' } as const, false)
// Set by compaction.ts while a main-chat compaction runs.
const compactingSince = atom({ plugin: 'asdev', key: 'compactingSince' } as const, 0)
// Set by compaction.ts at each main-thread reply: the moment the prompt cache was last refreshed.
const cacheAt = atom({ plugin: 'asdev', key: 'cacheAt' } as const, 0)

const k = (n: number) => `${Math.round(n / 1000)}k`

// One bar: `used` and the ticks are fractions of the whole (0..1); a tick is an arrow above it.
function bar(width: number, used: number, ticks: { at: number; faint?: boolean }[]): string {
  const x = (f: number) => Math.min(width, Math.max(0, f * width))
  const stops = HEAT.map(([at, c]) => `<stop offset="${at}" stop-color="${c}"/>`).join('')
  const arrows = ticks
    .filter(t => t.at > 0 && t.at < 1)
    .map(t => `<polygon points="${x(t.at) - 4},0 ${x(t.at) + 4},0 ${x(t.at)},5" fill="${t.faint ? '#8888' : '#888'}"/>`)
    .join('')
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${H}" viewBox="0 0 ${width} ${H}">`
    + `<defs><linearGradient id="heat" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="${width}" y2="0">${stops}</linearGradient></defs>`
    + `<rect y="${BAR_Y}" width="${width}" height="${BAR}" rx="4" fill="#8884"/>`
    + `<rect y="${BAR_Y}" width="${x(used)}" height="${BAR}" rx="4" fill="url(#heat)"/>`
    + arrows + '</svg>'
}

// The cache ring empties as the cache runs out: `left` is the fraction of its life still to run.
function ring(left: number, colour: string): string {
  const c = 2 * Math.PI * 7
  return '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 18 18">'
    + '<circle cx="9" cy="9" r="7" fill="none" stroke="#8884" stroke-width="3"/>'
    + `<circle cx="9" cy="9" r="7" fill="none" stroke="${colour}" stroke-width="3" stroke-dasharray="${(c * left).toFixed(1)} ${c.toFixed(1)}" transform="rotate(-90 9 9)"/>`
    + '</svg>'
}

// The collapsed band: two thin bars, the first fraction above the second.
function mini(top: number, bottom: number): string {
  const stops = HEAT.map(([at, c]) => `<stop offset="${at}" stop-color="${c}"/>`).join('')
  const row = (y: number, f: number) => `<rect y="${y}" width="28" height="3" rx="1.5" fill="#8884"/>`
    + `<rect y="${y}" width="${(28 * Math.min(1, Math.max(0, f))).toFixed(1)}" height="3" rx="1.5" fill="url(#heat)"/>`
  return '<svg xmlns="http://www.w3.org/2000/svg" width="28" height="10" viewBox="0 0 28 10">'
    + `<defs><linearGradient id="heat" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="28" y2="0">${stops}</linearGradient></defs>`
    + row(1, top) + row(6, bottom) + '</svg>'
}

function blocks(used: number, pace?: number, cells = 20): string {
  const filled = Math.min(cells, Math.round(used * cells))
  const cell = (i: number) => (pace !== undefined && i === Math.round(pace * cells) ? '│' : i < filled ? '█' : '░')
  return Array.from({ length: cells }, (_, i) => cell(i)).join('')
}

type Row = { name: string; label: string; width: number; used: number; ticks: { at: number; faint?: boolean }[]; pace?: number; value: string; detail: string; alt: string; old?: boolean }

// Module-level on purpose: a reload cancels the old timer and starts this over with it.
let ticking = false
// Whether the figures have answered once; until then a draw does not wait on them (see FIRST_WAIT).
let answered = false

export const register: Register = on => {
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    // Shown even collapsed: the app gives no sign of a compaction it did not start (traps.md, Mods).
    const since = await read($, compactingSince)
    if (since && !e.props.hasSurvey) {
      const { Text } = $.ui.resolve(e)
      const s = Math.round(((await $.clock.now()) - since) / 1000)
      return <Text>Compacting the conversation… {s} s (about a minute; a message sent now waits)</Text>
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
    ])
    const got = answered ? await figures : await Promise.race([figures, $.clock.sleep(FIRST_WAIT).then(() => undefined)])
    if (got) {
      answered = true
    } else {
      void figures.then(() => { answered = true; $.ui.invalidate('ui.render') })
    }
    const [usage, settings, kept] = got ?? []
    const context = usage?.context
    const cost = usage?.cost
    // Until the session's first reply the engine has no limit figures; the last ones any session saw
    // stand in, drawn faint.
    const old = !usage?.rateLimits.length
    const rateLimits = (old ? kept : usage?.rateLimits) ?? []

    // The window the session compacts against is the setting when one is set, not the model's.
    const setting = settings?.autoCompactWindow
    const limit = context ? Math.min(context.window, setting ?? context.window) : 0
    const compactAt = limit - COMPACT_MARGIN
    // Absent in a fresh session and after a compaction or relaunch until the next reply; the band
    // stays up rather than vanishing (it hid itself whole here before, 2026-10-02).
    const tokens = context?.tokens
    const now = await $.clock.now()
    const usd = cost ? `$${cost.usd.toFixed(2)}` : ''

    const shown = !limit ? '…' : `${tokens === undefined ? '–' : k(tokens)} / ${k(limit)}`
    const list: Row[] = [{
      name: 'Context',
      label: 'Context',
      width: W,
      used: limit ? (tokens ?? 0) / limit : 0,
      ticks: limit ? [{ at: TIDY_AT / limit, faint: true }, { at: compactAt / limit }] : [],
      value: shown,
      // Kept short: a long line wraps the band onto an extra row (owner, 2026-10-02). The ticks show
      // the tidy and compaction points; the alt text names them.
      detail: shown + (usd ? ` · ${usd}` : ''),
      alt: limit ? `tidy at ${k(TIDY_AT)}, compacts ~${k(compactAt)}` : 'loading',
      old: !limit,
    }]

    // The pace arrow is the share of the window already elapsed: staying left of it means the
    // limit lasts until it resets.
    for (const r of rateLimits) {
      const span = WINDOW_MS[r.kind]
      const resets = r.resetsAt ? Date.parse(r.resetsAt) : NaN
      const pace = span && !Number.isNaN(resets)
        ? Math.min(1, Math.max(0, 1 - (resets - now) / span))
        : undefined
      // A kept figure from a window that has since reset says nothing about the new one.
      const gone = old && !(resets > now)
      const used = gone ? 0 : r.percentUsed / 100
      const ahead = pace !== undefined && used > pace
      const h = Math.max(0, Math.round((resets - now) / 3600_000))
      const when = Number.isNaN(resets) ? '' : h < 48 ? `${h}h` : `${Math.round(h / 24)}d`
      list.push({
        name: LIMIT_NAME[r.kind] ?? r.kind,
        label: LIMIT_LABEL[r.kind] ?? r.kind,
        width: LIMIT_WIDTH[r.kind] ?? W,
        used,
        ticks: pace === undefined ? [] : [{ at: pace }],
        pace,
        value: gone ? '–' : `${r.percentUsed}%` + (when ? ` · ${when}` : ''),
        detail: gone ? '–' : `${r.percentUsed}%` + (when ? ` · resets ${when}` : ''),
        old,
        alt: (when ? `resets in ${when}` : '') + (pace === undefined ? '' : `, pace ${Math.round(pace * 100)}%${ahead ? ', ahead of pace' : ''}`),
      })
    }
    // Nothing to stand in yet: the rows still show, waiting.
    if (!got && !rateLimits.length) {
      for (const kind of ['five_hour', 'seven_day']) {
        list.push({ name: LIMIT_NAME[kind], label: LIMIT_LABEL[kind], width: LIMIT_WIDTH[kind] ?? W, used: 0, ticks: [], value: '…', detail: '…', alt: 'loading', old: true })
      }
    }

    // None before the first reply: there is no cache to time yet.
    const at = await read($, cacheAt)
    // The countdown moves with no new figures, so the band redraws itself each minute once it has one.
    // Started here rather than at session start, which a hot reload does not repeat for a live session.
    if (at && !ticking) {
      ticking = true
      $.clock.every(60_000, () => $.ui.invalidate('ui.render'))
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
              <Text dimColor>{r.name.padEnd(7)} {blocks(r.used, r.pace)} {r.detail}</Text>
              {i === 0 && cache ? <Text key="cache" color={cache.colour}>· cache {cache.text}</Text> : null}
              {i === 0 ? <Button key="hide" label="x" plain onPress={collapse} /> : null}
            </Box>
          ))}
        </Box>
      )
    }

    const { Box, Button, Svg, Text } = $.ui.resolve(e)
    return (
      <Box flexDirection="row" flexWrap="wrap" alignItems="center" columnGap={2} rowGap={1}>
        {list.map(r => (
          <Box key={r.name} flexDirection="row" alignItems="center" gap={1}>
            <Text dimColor>{r.label}</Text>
            <Svg source={bar(r.width, r.used, r.ticks)} alt={`${r.name}: ${r.value}${r.old && r.alt !== 'loading' ? ' (last known)' : ''}${r.alt ? `, ${r.alt}` : ''}`} />
            {r.old ? <Text dimColor>{r.value}</Text> : <Text bold>{r.value}</Text>}
          </Box>
        ))}
        {cache ? (
          <Box key="cache" flexDirection="row" alignItems="center" gap={1}>
            <Svg source={ring(cache.left, cache.colour)} alt={`Prompt cache: ${cache.text}${left > 0 ? ' left' : ''}`} />
            <Text dimColor>Cache</Text>
            <Text bold color={cache.colour}>{cache.text}</Text>
          </Box>
        ) : null}
        <Box key="end" flexDirection="row" alignItems="center" gap={1} flexGrow={1} justifyContent="flex-end">
          {usd ? <Text bold>{usd}</Text> : null}
          <Button key="hide" label="✕" role="dismiss" onPress={collapse} />
        </Box>
      </Box>
    )
  })

  // New figures redraw the band at once, not at the app's next unrelated redraw.
  on('session.measure', async ($, e, next) => {
    $.ui.invalidate('ui.render')
    // Kept for the next session's first draw, before its own first reply.
    if (e.changed.includes('rateLimits') && e.rateLimits.length) {
      await $.store.set('limits', e.rateLimits)
    }
    return next(e)
  })

  // Collapsed, the band becomes one button in the footer below the prompt.
  on('ui.render', { component: 'SessionMode' }, async ($, e, next) => {
    if (!(await read($, isCollapsed))) {
      return next(e)
    }
    // Two small bars, 5 hours above the week, in place of a word (owner, 2026-10-03).
    const got = await Promise.race([
      Promise.all([$.session.usage(), $.store.get('limits') as Promise<SessionRateLimit[] | undefined>]),
      $.clock.sleep(FIRST_WAIT).then(() => undefined),
    ])
    const fresh = got?.[0].rateLimits ?? []
    const shown = fresh.length ? fresh : got?.[1] ?? []
    const now = await $.clock.now()
    const used = (kind: string) => {
      const r = shown.find(x => x.kind === kind)
      // A kept figure from a window that has since reset says nothing about the new one.
      return !r || (!fresh.length && !(Date.parse(r.resetsAt ?? '') > now)) ? 0 : r.percentUsed / 100
    }
    const [hours, week] = [used('five_hour'), used('seven_day')]
    const show = () => update($, isCollapsed, () => false)
    const { Box, Button, Text } = $.ui.resolve(e)
    const modes = e.props.modes.length ? <Text dimColor>{e.props.modes.join(' & ')}</Text> : null
    if (e.surface === 'terminal') {
      return (
        <Box flexDirection="row" gap={1}>
          {modes}
          <Button key="show" label={`${blocks(hours, undefined, 4)} ${blocks(week, undefined, 4)}`} plain onPress={show} />
        </Box>
      )
    }
    // A desktop Button holds only a label, so the bars are drawn beside a one-glyph button that opens the band.
    const { Svg } = $.ui.resolve(e)
    return (
      <Box flexDirection="row" alignItems="center" gap={1}>
        {modes}
        <Svg source={mini(hours, week)} alt={`5 hours ${Math.round(hours * 100)}%, week ${Math.round(week * 100)}%`} />
        <Button key="show" label="▴" plain dimColor onPress={show} />
      </Box>
    )
  })
}
