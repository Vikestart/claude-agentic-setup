import { atom, read, update } from 'claude-code'
import type { EngineInterface as Engine, SessionRateLimit } from 'claude-code'

// The band shows the owner how full the usage windows are; the model never sees it. Past these lines
// the main chat is told to bring the docs up to date as for a handover, so work cut off at the limit
// picks up after the reset; at the second line again, with what came since. Notes only, never a
// block, and never to agents, which own no docs (owner, 2026-10-31).
const LINES: Record<string, { name: string; at: number[] }> = {
  five_hour: { name: '5-hour', at: [90, 95] },
  seven_day: { name: 'weekly', at: [98, 99] },
}
const HANDOVER = 'as if preparing a handover (the `asdev-handover` skill, short of its paste-ready message), '
  + 'so the work can stop at the limit and pick up after the reset with nothing lost.'
const FIRST = 'The owner asks you to bring all the documentation up to date now, ' + HANDOVER
const AGAIN = 'The limit is close. The owner asks you to bring all the documentation up to date again with '
  + 'everything since, ' + HANDOVER

type Noted = Record<string, { line: number; resetsAt?: string }>
// Per chat, so each chat hears of a line once per window; compaction.ts clears it, since the summary
// may drop the note.
const limitNoted =atom({ plugin: 'asdev', key: 'limitNoted' } as const, {} as Noted)

type Hit = { r: SessionRateLimit; line: number; top: boolean; resets: number }

function inFor(ms: number): string {
  const min = Math.max(1, Math.round(ms / 60_000))
  const h = Math.floor(min / 60), m = min % 60
  if (h >= 48) return `${Math.floor(h / 24)} days${h % 24 ? ` ${h % 24} h` : ''}`
  return h ? `${h} h${m ? ` ${m} min` : ''}` : `${m} min`
}

const lead = (h: Hit, now: number) => `The owner's ${LINES[h.r.kind].name} usage is at ${Math.floor(h.r.percentUsed)}%`
  + (Number.isNaN(h.resets) ? '' : ` and resets in ${inFor(h.resets - now)}`) + '. '

// The windows past a line, from the newest figure any chat saw (band.tsx keeps it); a window whose
// reset has passed is skipped, its figure stale.
async function crossed($: Engine, now: number): Promise<Hit[]> {
  const kept = await $.store.get('limits')
  return (Array.isArray(kept) ? kept as SessionRateLimit[] : []).flatMap(r => {
    const l = LINES[r.kind]
    const resets = Date.parse(r.resetsAt ?? '')
    if (!l || typeof r.percentUsed !== 'number' || resets <= now) return []
    const line = l.at.filter(a => r.percentUsed >= a).pop()
    return line === undefined ? [] : [{ r, line, top: line === l.at[l.at.length - 1], resets }]
  })
}

// The notes due now: each line the main chat has not heard of in this window.
export async function limitNotes($: Engine): Promise<string[]> {
  const now = await $.clock.now()
  const hits = await crossed($, now)
  const noted = await read($, limitNoted)
  const due = hits.filter(h => {
    const p = noted[h.r.kind]
    return !p || Date.parse(p.resetsAt ?? '') <= now || h.line > p.line
  })
  if (!due.length) return []
  await update($, limitNoted, n => ({ ...n, ...Object.fromEntries(due.map(h => [h.r.kind, { line: h.line, resetsAt: h.r.resetsAt }])) }))
  return due.map(h => lead(h, now) + (h.top ? AGAIN : FIRST))
}
