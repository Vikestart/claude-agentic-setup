import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'

// The test's hooks stand for the engine beneath the mod: context size, the compact command, the compaction.
function world(on: On, tokens: { now: number; goal?: string; step?: number; types?: Record<string, string> }) {
  const ran: { command: string; args?: string }[] = []
  const compacted: (string | undefined)[] = []
  on('session.usage', async () => ({ value: { startedAt: 0, rateLimits: [], context: { tokens: tokens.now, window: 1_000_000 } } }) as never)
  on('turn.complete', async () => ({ text: '' }) as never)
  for (const ev of ['ui.toast', 'ui.status', 'ui.invalidate'] as const) on(ev, async () => ({ value: undefined }) as never)
  on('command.run', async (_$, e) => { ran.push({ command: e.command, args: e.args }); return { text: '' } as never })
  on('session.compact', async (_$, e) => { compacted.push(e.instructions); return { messages: e.messages } as never })
  on('tool.call', async () => ({ result: 'ok' }) as never)
  on('classic.SessionStart', async () => ({}) as never)
  // A /goal's Stop hook, when `goal` is set: it blocks every stop with its check as the reason.
  on('classic.Stop', async () => (tokens.goal ? { block: tokens.goal } : {}) as never)
  const submitted: string[] = []
  on('prompt.submit', async (_$, e) => { submitted.push(e.text); return { text: e.text } as never })
  // A model request's usage: the context a subagent's loop is at.
  on('turn.step', async function* (_$, e) {
    const usage = { input_tokens: 1000, output_tokens: 10, cache_read_input_tokens: (tokens.step ?? 0) - 1000, cache_creation_input_tokens: 0, model: 'm' }
    return { turnId: e.turnId, index: e.index, answer: '', toolUses: [], stopReason: 'tool_use', usage } as never
  })
  on('agent.list', async () => ({ value: Object.entries(tokens.types ?? {}).map(([id, type]) => ({ id, type, description: '', status: 'running' })) }) as never)
  return { ran, compacted, submitted }
}

const MSGS = [{ role: 'user', text: 'hello', toolUses: [] }] as never

const turn = (answer: string, extra: object = {}) =>
  ({ answer, durationMs: 1, isAborted: false, turnId: 't', reason: 'answer', ...extra }) as never

const read = ($: any) => $.tool.call({ tool: 'Read', tool_use_id: `u${Math.random()}`, file_path: 'x' })

test('checkpoints armed at 150k, then a nudge every +50k, main chat only', async ($: any, on) => {
  mock.clock(on)
  const t = { now: 149_000 }
  world(on, t)
  expect((await read($)).context ?? []).toEqual([])
  t.now = 150_000
  const first = (await read($)).context?.[0]
  expect(first).toContain('checkpoint')
  expect(first).toContain('ready to compact')
  t.now = 199_000
  expect((await read($)).context ?? []).toEqual([])
  t.now = 200_000
  const second = (await read($)).context?.[0]
  expect(second).toContain('next clean break')
  expect(second).not.toContain('checkpoint the plan marks')
  expect(second).toContain('fine up to about 230k')
  expect(second).not.toContain('Start nothing new')
  t.now = 240_000
  expect((await read($)).context ?? []).toEqual([])
  t.now = 250_000
  const careful = (await read($)).context?.[0]
  expect(careful).toContain('past 230k')
  expect(careful).toContain('Start nothing new')
  expect(careful).toContain('ready to compact')
  expect(careful).toContain('Never pass 280k with the docs not updated')
  t.now = 400_000
  const agent = await $.tool.call({ tool: 'Read', tool_use_id: 'a1', agentId: 'agent-1', file_path: 'x' })
  expect(agent.context ?? []).toEqual([])
})

test('past 280k with the docs not updated since 230k, only the docs, searches, git reads and asking or waiting run', async ($: any, on) => {
  mock.clock(on)
  const t = { now: 290_000 }
  world(on, t)
  on('session.cwd', async () => ({ value: '/p' }) as never)
  on('fs.exists', async (_$, e) => (String((e as any).path ?? e).replace(/\\/g, '/').endsWith('.docs/task.md') ? { value: true } : { value: false }) as never)
  const call = (e: object) => $.tool.call({ tool_use_id: `u${Math.random()}`, ...e })
  expect((await call({ tool: 'Bash', command: 'npm run build' })).deny).toContain('.docs have not been updated')
  expect((await call({ tool: 'Read', file_path: 'src/app.ts' })).deny).toContain('past 280k')
  for (const e of [{ tool: 'Read', file_path: '/p/.docs/task.md' }, { tool: 'Grep', pattern: 'x' }, { tool: 'Bash', command: 'git status --short' },
    { tool: 'AskUserQuestion', questions: [] }, { tool: 'TaskStop', task_id: 'b1' }, { tool: 'Monitor', command: 'x' }, { tool: 'ToolSearch', query: 'select:Monitor' }]) {
    expect((await call(e)).deny).toBeUndefined()
  }
  // A docs write before 230k does not count; one after it lifts the hold until the next compaction.
  t.now = 220_000
  await call({ tool: 'Edit', file_path: 'C:\\p\\.docs\\task.md', old_string: 'a', new_string: 'b' })
  t.now = 290_000
  expect((await call({ tool: 'Bash', command: 'npm run build' })).deny).toContain('past 280k')
  await call({ tool: 'Write', file_path: '/p/.docs/task.md', content: 'state' })
  expect((await call({ tool: 'Bash', command: 'npm run build' })).deny).toBeUndefined()
  await $.session.compact({ messages: MSGS, trigger: 'manual' })
  expect((await call({ tool: 'Bash', command: 'npm run build' })).deny).toContain('past 280k')
  // So does /clear: the chat before's docs write says nothing about this one's.
  await call({ tool: 'Write', file_path: '/p/.docs/task.md', content: 'state' })
  await $.classic.SessionStart({ source: 'clear', cwd: '/p' })
  expect((await call({ tool: 'Bash', command: 'npm run build' })).deny).toContain('past 280k')
  // A subagent is never held.
  expect((await call({ tool: 'Bash', command: 'npm run build', agentId: 'agent-9' })).deny).toBeUndefined()
})

test('past 280k a project without .docs is not held', async ($: any, on) => {
  mock.clock(on)
  world(on, { now: 290_000 })
  on('session.cwd', async () => ({ value: '/p' }) as never)
  on('fs.exists', async () => ({ value: false }) as never)
  expect((await $.tool.call({ tool: 'Bash', tool_use_id: 'b1', command: 'npm run build' })).deny).toBeUndefined()
})

const stop = ($: any, text: string) =>
  $.classic.Stop({ hook_event_name: 'Stop', session_id: 's', transcript_path: 't', cwd: '/p', stop_hook_active: true, last_assistant_message: text })
const tick = () => new Promise(r => setTimeout(r, 0))

test('the trigger line compacts with the instructions, from 150k only', async ($: any, on) => {
  mock.clock(on)
  const t = { now: 149_000 }
  const w = world(on, t)
  await $.turn.complete(turn('Docs updated.\n\nready to compact'))
  await tick()
  expect(w.ran).toEqual([])
  t.now = 160_000
  await $.turn.complete(turn('Docs updated.\n\n`Ready to compact.`'))
  await tick()
  expect(w.ran.map(r => r.command)).toEqual(['compact'])
  expect(w.ran[0].args).toContain('Keep: the current phase')
})

test('no trigger: the line mid-reply, an aborted turn, a subagent', async ($: any, on) => {
  mock.clock(on)
  const w = world(on, { now: 300_000 })
  await $.turn.complete(turn('ready to compact\nbut first one more step'))
  await $.turn.complete(turn('ready to compact', { isAborted: true, reason: 'aborted' }))
  await $.turn.complete(turn('ready to compact', { agentId: 'agent-1' }))
  await tick()
  expect(w.ran).toEqual([])
})

test('a reply that asks the owner is not compacted; the nudge comes back on the next tool call', async ($: any, on) => {
  mock.clock(on)
  const t = { now: 152_000 }
  const w = world(on, t)
  expect((await read($)).context?.[0]).toContain('Never in a reply that asks the owner')
  expect((await read($)).context ?? []).toEqual([])
  await $.turn.complete(turn('Canvas published.\n\n**Which directions do you pick?**\n\nready to compact'))
  await tick()
  expect(w.ran).toEqual([])
  expect((await read($)).context?.[0]).toContain('next clean break')
  // A question inside a fenced paste-ready note is not one to the owner.
  await $.turn.complete(turn('Paste this:\n```\nWhich phase is next?\n```\nready to compact'))
  await tick()
  expect(w.ran.map(r => r.command)).toEqual(['compact'])
})

// Under /goal the goal's Stop hook blocks every stop: the turn never ends, so the trigger never reaches
// turn.complete. The mod lets that one stop through and hands the goal's check back after the compaction.
test('under /goal: the trigger stop is let through, and the goal is carried on after', async ($: any, on) => {
  mock.clock(on)
  const w = world(on, { now: 300_000, goal: 'Round 2 has not happened yet.' })
  expect((await stop($, 'still working')).block).toBe('Round 2 has not happened yet.')
  expect((await stop($, 'Docs updated.\nready to compact')).block).toBeUndefined()
  expect(w.submitted).toEqual([])
  await $.session.compact({ trigger: 'manual', instructions: 'x', messages: MSGS })
  await tick()
  expect(w.submitted.length).toBe(1)
  expect(w.submitted[0]).toContain('Round 2 has not happened yet.')
  await $.session.compact({ trigger: 'auto', messages: MSGS })
  await tick()
  expect(w.submitted.length).toBe(1)
})

// "Truthful state": a claimed push with commits still ahead of the upstream is sent back, once.
test('a reply claiming a push while commits are unpushed is sent back once; true or negated claims stop', async ($: any, on) => {
  mock.clock(on)
  world(on, { now: 1000 })
  const status = { out: '## main...origin/main [ahead 2]\n M x.php\n' }
  on('process.run', async () => ({ value: { exitCode: 0, stdout: status.out, stderr: '' } }) as never)
  const first = (text: string) =>
    $.classic.Stop({ hook_event_name: 'Stop', session_id: 's', transcript_path: 't', cwd: '/p', stop_hook_active: false, last_assistant_message: text })
  const r = await first('Committed and pushed to main.')
  expect(r.block).toContain('2 commit(s) ahead of origin/main')
  expect((await stop($, 'Committed and pushed to main.')).block).toBeUndefined()
  for (const text of ['Committed; not pushed yet.', "It isn't merged.", 'Nothing was deployed.', 'Two unpushed commits remain.', 'Tests pass.']) {
    expect((await first(text)).block).toBeUndefined()
  }
  status.out = '## main...origin/main\n'
  expect((await first('Merged and pushed.')).block).toBeUndefined()
})

// The store and session id the start is kept under, and how many replies the transcript holds;
// registered before the first `$` call.
function kept(on: any, store: Record<string, unknown>, replies = 0) {
  on('session.id', async () => ({ value: 's1' }) as never)
  on('session.messages', async () => ({ value: Array.from({ length: replies }, () => ({ role: 'assistant', text: '', toolUses: [] })) }) as never)
  on('store.get', async (_$: any, e: any) => ({ value: store[e.key] }) as never)
  on('store.set', async (_$: any, e: any) => { store[e.key] = e.value; return { value: undefined } as never })
}

test('the first note comes 100k past where the chat started, and never past 230k', async ($: any, on) => {
  mock.clock(on)
  const store: Record<string, unknown> = {}
  kept(on, store)
  const t = { now: 0, step: 90_000 }
  world(on, t)
  await $.classic.SessionStart({ source: 'startup', cwd: '/p' })
  await step($, undefined as never)
  // Only the first reply measures the start.
  t.step = 150_000
  await step($, undefined as never)
  t.now = 160_000
  expect(notes(await read($))).toBe('')
  t.now = 190_000
  expect(notes(await read($))).toContain('checkpoint the plan marks')
  // A compaction measures again: a chat that comes back at 180k is first asked at 230k, not 280k.
  await $.session.compact({ trigger: 'auto', messages: MSGS })
  await tick()
  await $.classic.SessionStart({ source: 'compact', cwd: '/p' })
  t.step = 180_000
  await step($, undefined as never)
  t.now = 229_000
  expect(notes(await read($))).toBe('')
  t.now = 230_000
  expect(notes(await read($))).toContain('ready to compact')
  expect(store.contextBases).toEqual({ s1: 180_000 })
})

test('a reopened chat keeps the start it had, and the trigger line waits for it too', async ($: any, on) => {
  mock.clock(on)
  const store: Record<string, unknown> = { contextBases: { s0: 40_000, s1: 120_000 } }
  kept(on, store)
  const t = { now: 210_000, step: 210_000 }
  const w = world(on, t)
  await $.classic.SessionStart({ source: 'startup', cwd: '/p' })
  await step($, undefined as never)
  expect(notes(await read($))).toBe('')
  await $.turn.complete(turn('Docs updated.\n\nready to compact'))
  await tick()
  expect(w.ran).toEqual([])
  t.now = 220_000
  expect(notes(await read($))).toContain('ready to compact')
  await $.turn.complete(turn('Docs updated.\n\nready to compact'))
  await tick()
  expect(w.ran.map(r => r.command)).toEqual(['compact'])
  expect(store.contextBases).toEqual({ s0: 40_000, s1: 120_000 })
})

test('a compaction that never finished keeps the start, and the note comes again at once', async ($: any, on) => {
  mock.clock(on)
  const store: Record<string, unknown> = {}
  kept(on, store)
  const t = { now: 0, step: 60_000 }
  world(on, t)
  await $.classic.SessionStart({ source: 'startup', cwd: '/p' })
  await step($, undefined as never)
  t.now = 170_000
  expect(notes(await read($))).toContain('checkpoint the plan marks')
  // Cancelled or failed: no compact start follows, and the context is still 170k.
  await $.session.compact({ trigger: 'manual', messages: MSGS })
  await tick()
  t.step = 172_000
  await step($, undefined as never)
  t.now = 172_000
  expect(notes(await read($))).toContain('checkpoint the plan marks')
  expect(store.contextBases).toEqual({ s1: 60_000 })
})

test('a chat reopened with no start kept keeps the old 150k, not its size now', async ($: any, on) => {
  mock.clock(on)
  const store: Record<string, unknown> = {}
  kept(on, store, 12)
  const t = { now: 0, step: 180_000 }
  world(on, t)
  await $.classic.SessionStart({ source: 'startup', cwd: '/p' })
  await step($, undefined as never)
  t.now = 150_000
  expect(notes(await read($))).toContain('checkpoint the plan marks')
  expect(store.contextBases).toBeUndefined()
})

test('/clear and a resume start afresh: no stale start, nudge or docs mark from the chat before', async ($: any, on) => {
  mock.clock(on)
  const store: Record<string, unknown> = {}
  kept(on, store)
  const t = { now: 0, step: 40_000 }
  world(on, t)
  await $.classic.SessionStart({ source: 'startup', cwd: '/p' })
  await step($, undefined as never)
  t.now = 250_000
  expect(notes(await read($))).toContain('ready to compact')
  // Without the reset the next note would wait for 300k, past the automatic compaction.
  await $.classic.SessionStart({ source: 'clear', cwd: '/p' })
  t.step = 30_000
  await step($, undefined as never)
  t.now = 130_000
  expect(notes(await read($))).toContain('checkpoint the plan marks')
  // The resumed chat's kept start counts, not the one this process measured last.
  store.contextBases = { s1: 120_000 }
  await $.classic.SessionStart({ source: 'resume', cwd: '/p' })
  t.now = 200_000
  expect(notes(await read($))).toBe('')
  t.now = 220_000
  expect(notes(await read($))).toContain('checkpoint the plan marks')
})

test('without a blocking Stop hook, or below 150k, a stop is left alone', async ($: any, on) => {
  mock.clock(on)
  const t: { now: number; goal?: string } = { now: 300_000 }
  const w = world(on, t)
  expect((await stop($, 'ready to compact')).block).toBeUndefined()
  t.now = 100_000
  t.goal = 'not done'
  expect((await stop($, 'ready to compact')).block).toBe('not done')
  await $.session.compact({ trigger: 'auto', messages: MSGS })
  await tick()
  expect(w.submitted).toEqual([])
})

test('instructions added only when none are given, the subagent kind to subagents', async ($: any, on) => {
  mock.clock(on)
  const w = world(on, { now: 300_000 })
  await $.session.compact({ trigger: 'auto', messages: MSGS })
  await $.session.compact({ trigger: 'manual', instructions: 'mine', messages: MSGS })
  await $.session.compact({ trigger: 'auto', agentId: 'agent-1', messages: MSGS })
  expect(w.compacted[0]).toContain('Keep: the current phase')
  expect(w.compacted[1]).toBe('mine')
  expect(w.compacted[2]).toContain('This is a subagent')
})

test('after a compaction: names the docs and restores the last reply verbatim', async ($: any, on) => {
  mock.clock(on)
  world(on, { now: 300_000 })
  on('fs.exists', async (_$, e) => (String((e as any).path ?? e).replace(/\\/g, '/').endsWith('.docs/task.md') ? { value: true } : { value: false }) as never)
  on('process.run', async () => ({ value: { exitCode: 0, stdout: '[]', stderr: '' } }) as never)
  await $.turn.complete(turn('Step 2 is done. What next?'))
  const r = await $.classic.SessionStart({ source: 'compact', cwd: '/p' })
  const text = (r.additionalContext ?? []).join('\n')
  expect(text).toContain('re-read .docs/task.md')
  expect(text).not.toContain('implementation_plan')
  expect(text).toContain('<<<\nStep 2 is done. What next?\n>>>')
  const plain = await $.classic.SessionStart({ source: 'startup', cwd: '/p' })
  expect(plain.additionalContext ?? []).toEqual([])
})

const step = async ($: any, agentId: string) => {
  const s = $.turn.step({ turnId: 't', index: 0, model: 'm', messageCount: 1, agentId })
  if (s && typeof s[Symbol.asyncIterator] === 'function') { for await (const _ of s) { /* drain */ } } else await s
}
const call = ($: any, agentId: string, tool = 'Read', extra: object = {}) =>
  $.tool.call({ tool, tool_use_id: `u${Math.random()}`, agentId, file_path: 'x', ...extra })
const notes = (r: any) => (r.context ?? []).join('\n')

test('a subagent: a split note at 125k with nothing written, a hand-back from 250k every +50k', async ($: any, on) => {
  mock.clock(on)
  const t = { now: 0, step: 120_000, types: { a1: 'opus-medium-executor' } }
  world(on, t)
  await step($, 'a1')
  expect(notes(await call($, 'a1'))).toBe('')
  t.step = 130_000
  await step($, 'a1')
  expect(notes(await call($, 'a1'))).toContain('not written anything yet')
  expect(notes(await call($, 'a1'))).toBe('')
  t.step = 260_000
  await step($, 'a1')
  expect(notes(await call($, 'a1'))).toContain('hand back')
  t.step = 300_000
  await step($, 'a1')
  expect(notes(await call($, 'a1'))).toBe('')
  t.step = 310_000
  await step($, 'a1')
  expect(notes(await call($, 'a1'))).toContain('310k')
})

test('no split note for an agent that wrote, or one that only reads by design', async ($: any, on) => {
  mock.clock(on)
  const t = { now: 0, step: 100_000, types: { w: 'opus-medium-executor', r: 'opus-high-reviewer', g: 'sonnet-medium-executor', x: 'opus-medium-executor' } }
  world(on, t)
  await step($, 'w')
  await step($, 'g')
  await step($, 'x')
  await call($, 'w', 'Edit')
  // A gate run through the shell is work done; a grep is still exploring.
  await call($, 'g', 'Bash', { command: 'python quiet.py -- pytest -q' })
  await call($, 'x', 'Bash', { command: 'grep -rn foo src' })
  t.step = 130_000
  await step($, 'w')
  await step($, 'g')
  await step($, 'x')
  await step($, 'r')
  expect(notes(await call($, 'w'))).toBe('')
  expect(notes(await call($, 'g'))).toBe('')
  expect(notes(await call($, 'x'))).toContain('not written anything')
  expect(notes(await call($, 'r'))).toBe('')
  t.step = 260_000
  await step($, 'r')
  expect(notes(await call($, 'r'))).toContain('hand back')
})

test('a builder at 250k is told to commit wip first; a reviewer is not', async ($: any, on) => {
  mock.clock(on)
  const t = { now: 0, step: 260_000, types: { b: 'opus-medium-executor', r: 'opus-medium-reviewer' } }
  world(on, t)
  await step($, 'b')
  await step($, 'r')
  expect(notes(await call($, 'b'))).toContain('`wip` commit')
  const review = notes(await call($, 'r'))
  expect(review).toContain('hand back')
  expect(review).not.toContain('wip')
})

test('a subagent rereading a whole unchanged file is refused; changed, partial, main chat and after a compaction run', async ($: any, on) => {
  mock.clock(on)
  world(on, { now: 0, step: 50_000 })
  const files: Record<string, string> = { '/p/doc.md': 'v1', '/p/other.md': 'x' }
  on('fs.read', async (_$, e: any) => ({ value: Object.entries(files).find(([n]) => String(e.path).replace(/\\/g, '/').endsWith(n))?.[1] ?? 'x' }) as never)
  on('session.cwd', async () => ({ value: '/p' }) as never)
  const rd = (agentId: string | undefined, extra: object = {}) =>
    $.tool.call({ tool: 'Read', tool_use_id: `u${Math.random()}`, file_path: '/p/doc.md', ...(agentId ? { agentId } : {}), ...extra })
  await step($, 'a1')
  await step($, 'a2')
  expect((await rd('a1')).deny).toBeUndefined()
  expect((await rd('a1')).deny).toContain('already read all of /p/doc.md')
  expect((await rd('a1', { offset: 10, limit: 20 })).deny).toBeUndefined()
  expect((await rd('a2')).deny).toBeUndefined()
  expect((await rd(undefined)).deny).toBeUndefined()
  expect((await rd(undefined)).deny).toBeUndefined()
  files['/p/doc.md'] = 'v2'
  expect((await rd('a1')).deny).toBeUndefined()
  await $.session.compact({ trigger: 'auto', agentId: 'a1', messages: MSGS })
  expect((await rd('a1')).deny).toBeUndefined()
})

// A reload mid-compaction leaves the old ticker's status line behind; the next load clears it, or
// picks the count back up while the compaction is still running.
test('a reload clears a frozen compaction status, or resumes a running one', async ($: any, on) => {
  const clock = mock.clock(on, { now: 10_000_000 })
  for (const ev of ['ui.toast', 'ui.invalidate'] as const) on(ev, async () => ({ value: undefined }) as never)
  on('session.start', async (_$, e: any) => ({ cwd: e.cwd }) as never)
  const status: (string | undefined)[] = []
  on('ui.status', async (_$, e: any) => { status.push(e.text); return { value: undefined } as never })
  on('prompt.submit', async (_$, e) => ({ text: e.text }) as never)
  let finish = () => {}
  on('session.compact', async (_$, e) => { await new Promise<void>(r => { finish = r }); return { messages: e.messages } as never })
  const start = () => $.session.start({ cwd: 'x', surface: null, isInteractive: true })

  // No compaction: whatever an earlier load left is cleared.
  await start()
  expect(status).toEqual([undefined])

  // A compaction still running: the count carries on through the reload.
  const done = $.session.compact({ trigger: 'auto', messages: [{ role: 'user', text: 'hi', toolUses: [] }] })
  await clock.advance(2000)
  status.length = 0
  await start()
  await clock.advance(1000)
  expect(status.length).toBeGreaterThan(0)
  expect(status.every(s => s?.includes('Compacting'))).toBe(true)

  // Once it ends the line clears as before.
  finish()
  await done
  await clock.advance(1000)
  expect(status.at(-1)).toBeUndefined()
})

// A compaction whose end is never seen (a reload lost the wait) stops counting after 10 minutes.
test('a compaction never seen to end stops counting after 10 minutes', async ($: any, on) => {
  const clock = mock.clock(on, { now: 10_000_000 })
  for (const ev of ['ui.toast', 'ui.invalidate'] as const) on(ev, async () => ({ value: undefined }) as never)
  const status: (string | undefined)[] = []
  on('ui.status', async (_$, e: any) => { status.push(e.text); return { value: undefined } as never })
  let finish = () => {}
  on('session.compact', async (_$, e) => { await new Promise<void>(r => { finish = r }); return { messages: e.messages } as never })
  const done = $.session.compact({ trigger: 'auto', messages: MSGS })
  await clock.advance(9 * 60_000)
  expect(status.at(-1)).toContain('Compacting')
  await clock.advance(60_000 + 1000)
  expect(status.at(-1)).toBeUndefined()
  finish()
  await done
})

test('what counts as asking: a closing ?, an aside after it, Y/N; not a ? mid-sentence or in code', async ($: any, on) => {
  mock.clock(on)
  const w = world(on, { now: 160_000 })
  const asking = ['Merge now? (I will wait.)', 'Approve the plan (Y/N)', 'Proceed? Y/N', 'Klar？', '## What changed?']
  const telling = ['It passed? Yes, all of it.', 'See `a?`.', 'It prints `[Y/N]` first.', '```\nok?\n```']
  for (const [i, text] of [...asking, ...telling].entries()) {
    await $.turn.complete(turn(`${text}\nready to compact`, { turnId: `t${i}` }))
    await tick()
  }
  expect(w.ran.length).toBe(telling.length)
})

// A queued message ran before the mod's /compact and its reply ended with the trigger too: a second
// /compact was queued and compacted the fresh summary again (work setup, seen 2026-10-27).
test('a trigger while its own /compact waits queues no second one', async ($: any, on) => {
  const clock = mock.clock(on, { now: 10_000_000 })
  on('session.usage', async () => ({ value: { startedAt: 0, rateLimits: [], context: { tokens: 160_000, window: 1_000_000 } } }) as never)
  on('turn.complete', async () => ({ text: '' }) as never)
  for (const ev of ['ui.toast', 'ui.status', 'ui.invalidate'] as const) on(ev, async () => ({ value: undefined }) as never)
  let runs = 0
  let finish = () => {}
  on('command.run', async () => {
    runs++
    await new Promise<void>(r => { finish = r })
    return { text: '' } as never
  })
  await $.turn.complete(turn('Paused.\n\nready to compact'))
  await clock.advance(2000)
  await $.turn.complete(turn('Yes, done.\n\nready to compact', { turnId: 't2' }))
  await clock.advance(2000)
  expect(runs).toBe(1)
  // Once it is done, a later trigger compacts again.
  finish()
  await clock.advance(2000)
  await $.turn.complete(turn('Docs updated.\n\nready to compact', { turnId: 't3' }))
  await clock.advance(2000)
  expect(runs).toBe(2)
})
