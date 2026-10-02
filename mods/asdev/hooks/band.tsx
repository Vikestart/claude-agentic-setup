import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

// Compaction lands about 33k below the window (measured 2026-10-01, main chats and agents alike).
const COMPACT_MARGIN = 33_000
// Past this a session should compact at its next clean break (roadmap: graceful compaction).
const TIDY_AT = 200_000
const WINDOW_MS: Record<string, number> = { five_hour: 5 * 3600_000, seven_day: 7 * 86400_000 }
const LIMIT_NAME: Record<string, string> = { five_hour: '5 hours', seven_day: 'Week' }

const GREEN = '#2e9e6a', AMBER = '#d4a017', RED = '#d9534f'
const W = 300, H = 12

const isCollapsed = atom({ plugin: 'asdev', key: 'isCollapsed' } as const, false)
// Set by compaction.ts while a main-chat compaction runs.
const compactingSince = atom({ plugin: 'asdev', key: 'compactingSince' } as const, 0)

const k = (n: number) => `${Math.round(n / 1000)}k`

// One bar: `used` and the ticks are fractions of the whole (0..1).
function bar(used: number, fill: string, ticks: { at: number; dashed?: boolean }[]): string {
  const x = (f: number) => Math.min(W, Math.max(0, f * W))
  const lines = ticks
    .filter(t => t.at > 0 && t.at < 1)
    .map(t => `<line x1="${x(t.at)}" y1="0" x2="${x(t.at)}" y2="${H}" stroke="#888" stroke-width="2"`
      + (t.dashed ? ' stroke-dasharray="3 2"' : '') + '/>')
    .join('')
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">`
    + `<rect width="${W}" height="${H}" rx="4" fill="#8884"/>`
    + `<rect width="${x(used)}" height="${H}" rx="4" fill="${fill}"/>`
    + lines + '</svg>'
}

function blocks(used: number, pace?: number, cells = 20): string {
  const filled = Math.min(cells, Math.round(used * cells))
  const cell = (i: number) => (pace !== undefined && i === Math.round(pace * cells) ? '│' : i < filled ? '█' : '░')
  return Array.from({ length: cells }, (_, i) => cell(i)).join('')
}

type Row = { name: string; used: number; fill: string; ticks: { at: number; dashed?: boolean }[]; pace?: number; detail: string; alt: string }

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

    const { context, cost, rateLimits } = await $.session.usage()

    // The window the session compacts against is the setting when one is set, not the model's.
    let setting: number | undefined
    try {
      setting = ((await $.settings.read()) as { autoCompactWindow?: number }).autoCompactWindow
    } catch {
      // Unreadable settings: the model's window still gives a usable bar.
    }
    const limit = Math.min(context.window, setting ?? context.window)
    const compactAt = limit - COMPACT_MARGIN
    // Absent in a fresh session and after a compaction or relaunch until the next reply; the band
    // stays up rather than vanishing (it hid itself whole here before, 2026-10-02).
    const tokens = context.tokens
    const now = await $.clock.now()

    const list: Row[] = [{
      name: 'Context',
      used: (tokens ?? 0) / limit,
      fill: tokens === undefined ? GREEN : tokens >= compactAt ? RED : tokens >= TIDY_AT ? AMBER : GREEN,
      ticks: [{ at: TIDY_AT / limit, dashed: true }, { at: compactAt / limit }],
      // Kept short: a long line wraps the band onto an extra row (owner, 2026-10-02). The ticks show
      // the tidy and compaction points; the alt text names them.
      detail: `${tokens === undefined ? '–' : k(tokens)} / ${k(limit)}` + (cost ? ` · $${cost.usd.toFixed(2)}` : ''),
      alt: `tidy at ${k(TIDY_AT)}, compacts ~${k(compactAt)}`,
    }]

    // The pace line is the share of the window already elapsed: staying left of it means the
    // limit lasts until it resets.
    for (const r of rateLimits) {
      const span = WINDOW_MS[r.kind]
      const resets = r.resetsAt ? Date.parse(r.resetsAt) : NaN
      const pace = span && !Number.isNaN(resets)
        ? Math.min(1, Math.max(0, 1 - (resets - now) / span))
        : undefined
      const used = r.percentUsed / 100
      const ahead = pace !== undefined && used > pace
      const h = Math.max(0, Math.round((resets - now) / 3600_000))
      const left = Number.isNaN(resets) ? '' : ` · resets ${h < 48 ? `${h}h` : `${Math.round(h / 24)}d`}`
      list.push({
        name: LIMIT_NAME[r.kind] ?? r.kind,
        used,
        // Amber already says "ahead of pace", and the tick is the pace.
        fill: used >= 0.9 ? RED : ahead ? AMBER : GREEN,
        ticks: pace === undefined ? [] : [{ at: pace }],
        pace,
        detail: `${r.percentUsed}%` + left,
        alt: pace === undefined ? '' : `pace ${Math.round(pace * 100)}%${ahead ? ', ahead of pace' : ''}`,
      })
    }

    const collapse = () => update($, isCollapsed, () => true)

    if (e.surface === 'terminal') {
      const { Box, Button, Text } = $.ui.resolve(e)
      return (
        <Box flexDirection="column">
          {list.map((r, i) => (
            <Box key={r.name} flexDirection="row" gap={1}>
              <Text dimColor>{r.name.padEnd(7)} {blocks(r.used, r.pace)} {r.detail}</Text>
              {i === 0 ? <Button key="hide" label="x" plain onPress={collapse} /> : null}
            </Box>
          ))}
        </Box>
      )
    }

    const { Box, Button, Svg, Text } = $.ui.resolve(e)
    return (
      <Box flexDirection="row" alignItems="flex-start" gap={1}>
        <Box flexDirection="column" flexGrow={1}>
          {list.map(r => (
            <Box key={r.name} flexDirection="row" alignItems="center" gap={1}>
              {/* A fixed width: padEnd aligns only in a monospace font, and the desktop's is not. */}
              <Box width={8} flexShrink={0}><Text dimColor>{r.name}</Text></Box>
              <Svg source={bar(r.used, r.fill, r.ticks)} alt={`${r.name}: ${r.detail}${r.alt ? `, ${r.alt}` : ''}`} />
              <Text dimColor>{r.detail}</Text>
            </Box>
          ))}
        </Box>
        <Button key="hide" label="✕" role="dismiss" onPress={collapse} />
      </Box>
    )
  })

  // New figures redraw the band at once, not at the app's next unrelated redraw.
  on('session.measure', async ($, e, next) => {
    $.ui.invalidate('ui.render')
    return next(e)
  })

  // Collapsed, the band becomes one button in the footer below the prompt.
  on('ui.render', { component: 'SessionMode' }, async ($, e, next) => {
    if (!(await read($, isCollapsed))) {
      return next(e)
    }
    const { Box, Button, Text } = $.ui.resolve(e)
    return (
      <Box flexDirection="row" gap={1}>
        {e.props.modes.length ? <Text dimColor>{e.props.modes.join(' & ')}</Text> : null}
        <Button key="show" label="Usage" plain onPress={() => update($, isCollapsed, () => false)} />
      </Box>
    )
  })
}
