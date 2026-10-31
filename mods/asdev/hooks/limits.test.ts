import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

const NOW = 1_000_000_000
const HOUR = 3600_000

// The kept figures stand for what band.tsx stored from replies and usage reads; the test's hooks for the engine beneath.
function world(on: On) {
  const clock = mock.clock(on, { now: NOW })
  const store: Record<string, unknown> = { limits: [] }
  on('store.get', async (_$, e) => ({ value: store[e.key] }) as never)
  on('store.set', async (_$, e) => { store[e.key] = e.value; return { value: undefined } as never })
  on('session.usage', async () => ({ value: { startedAt: 0, rateLimits: [], context: { tokens: 10_000, window: 1_000_000 } } }) as never)
  for (const ev of ['ui.toast', 'ui.status', 'ui.invalidate'] as const) on(ev, async () => ({ value: undefined }) as never)
  on('session.compact', async (_$, e) => ({ messages: e.messages }) as never)
  on('tool.call', async () => ({ result: 'ok' }) as never)
  const prompts: (readonly string[])[] = []
  on('prompt.submit', async (_$, e) => { prompts.push(e.context ?? []); return { text: e.text } as never })
  const set = (five?: number, week?: number, resets = NOW + 2 * HOUR) => {
    const resetsAt = new Date(resets).toISOString()
    store.limits = [
      ...(five === undefined ? [] : [{ kind: 'five_hour', percentUsed: five, resetsAt }]),
      ...(week === undefined ? [] : [{ kind: 'seven_day', percentUsed: week, resetsAt: new Date(NOW + 3 * 24 * HOUR).toISOString() }]),
    ]
  }
  return { clock, set, prompts }
}

const notes = async ($: any, agentId?: string) =>
  (await $.tool.call({ tool: 'Read', tool_use_id: `u${Math.random()}`, file_path: 'x', ...(agentId ? { agentId } : {}) })).context ?? []

test('the 5-hour window: a caution at 90%, a firmer note at 95%, each once', async ($: any, on) => {
  const w = world(on)
  w.set(89.9)
  expect(await notes($)).toEqual([])
  w.set(90.4)
  const first = await notes($)
  expect(first.length).toBe(1)
  expect(first[0]).toContain("The owner's 5-hour usage is at 90% and resets in 2 h.")
  expect(first[0]).toContain('bring all the documentation up to date now, as if preparing a handover')
  expect(first[0]).toContain('nothing lost')
  w.set(94)
  expect(await notes($)).toEqual([])
  await $.prompt.submit({ text: 'go on' })
  expect(w.prompts[0]).toEqual([])
  w.set(95)
  await $.prompt.submit({ text: 'go on' })
  expect(w.prompts[1].length).toBe(1)
  expect(w.prompts[1][0]).toContain('usage is at 95%')
  expect(w.prompts[1][0]).toContain('The limit is close')
  expect(w.prompts[1][0]).toContain('up to date again with everything since')
  expect(await notes($)).toEqual([])
})

test('the weekly window: lines at 98% and 99%, beside the 5-hour one', async ($: any, on) => {
  const w = world(on)
  w.set(50, 97.9)
  expect(await notes($)).toEqual([])
  w.set(91, 98)
  const both = await notes($)
  expect(both.length).toBe(2)
  expect(both[0]).toContain('5-hour usage is at 91%')
  expect(both[1]).toContain("The owner's weekly usage is at 98% and resets in 3 days.")
  expect(both[1]).toContain('up to date now')
  w.set(91, 99.2)
  const firm = await notes($)
  expect(firm.length).toBe(1)
  expect(firm[0]).toContain('weekly usage is at 99%')
  expect(firm[0]).toContain('The limit is close')
})

test('a new window notes again; a figure whose window has reset says nothing', async ($: any, on) => {
  const w = world(on)
  w.set(92, undefined, NOW + 10 * 60_000)
  expect((await notes($))[0]).toContain('resets in 10 min')
  await w.clock.advance(11 * 60_000)
  expect(await notes($)).toEqual([])
  w.set(91, undefined, NOW + 5 * HOUR)
  expect((await notes($))[0]).toContain('5-hour usage is at 91%')
})

test('a compaction may drop the note, so the next call repeats it', async ($: any, on) => {
  const w = world(on)
  w.set(93)
  expect((await notes($)).length).toBe(1)
  await $.session.compact({ trigger: 'auto', messages: [{ role: 'user', text: 'hi', toolUses: [] }] })
  expect((await notes($)).length).toBe(1)
})

test('agents own no docs, so they hear nothing; the main chat still does', async ($: any, on) => {
  const w = world(on)
  w.set(96, 99.5)
  expect(await notes($, 'agent-1')).toEqual([])
  expect((await notes($)).length).toBe(2)
})
