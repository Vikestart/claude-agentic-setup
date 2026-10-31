import { atom, read, update } from 'claude-code'
import type { EngineInterface as Engine, SessionRateLimit } from 'claude-code'

// The band shows the owner how full the usage windows are; the model never sees it. Past these lines
// the chat is told to go easy: the first a caution, the second firmer. Notes only, never a block
// (owner, 2026-10-31).
const LINES: Record<string, { name: string; at: number[] }> = {
  five_hour: { name: '5-hour', at: [90, 95] },
  seven_day: { name: 'weekly', at: [98, 99] },
}
const CAREFUL = 'Be careful with spend until then: work directly, keep reads, runs and output small, and '
  + 'spawn no subagent without asking the owner first.'
const CLOSE = 'The limit is close: spawn no subagent unless the owner asks for one, start no long run or '
  + 'wide read, finish the current step in as few turns as possible, and tell the owner where things stand.'
const AGENT = 'Finish the current step, then hand back what is done, what is left and the exact next step; '
  + 'start nothing new.'

type Noted = Record<string, { line: number; resetsAt?: string }>
// Per chat, so each chat hears of a line once per window; compaction.ts clears it, since the summary
// may drop the note.
const limitNoted =atom({ plugin: 'asdev', key: 'limitNoted' } as const, {} as Noted)
// An agent hears only the firmer line, once. A reload starts it over: at most one repeated note.
const agentsNoted = new Set<string>()

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

// The notes due now: for the main chat a line it has not heard of in this window, for an agent the firmer line.
export async function limitNotes($: Engine, agentId?: string): Promise<string[]> {
  const now = await $.clock.now()
  const hits = await crossed($, now)
  if (agentId) {
    const due = hits.filter(h => h.top && !agentsNoted.has(`${agentId} ${h.r.kind} ${h.r.resetsAt}`))
    for (const h of due) agentsNoted.add(`${agentId} ${h.r.kind} ${h.r.resetsAt}`)
    return due.map(h => lead(h, now) + AGENT)
  }
  const noted = await read($, limitNoted)
  const due = hits.filter(h => {
    const p = noted[h.r.kind]
    return !p || Date.parse(p.resetsAt ?? '') <= now || h.line > p.line
  })
  if (!due.length) return []
  await update($, limitNoted, n => ({ ...n, ...Object.fromEntries(due.map(h => [h.r.kind, { line: h.line, resetsAt: h.r.resetsAt }])) }))
  return due.map(h => lead(h, now) + (h.top ? CLOSE : CAREFUL))
}
