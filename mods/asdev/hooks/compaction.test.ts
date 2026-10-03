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
  on('prompt.submit', async (_$, e) => { submitted.push(e.text); return {} as never })
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
  t.now = 240_000
  expect((await read($)).context ?? []).toEqual([])
  t.now = 250_000
  expect((await read($)).context?.[0]).toContain('250k')
  t.now = 400_000
  const agent = await $.tool.call({ tool: 'Read', tool_use_id: 'a1', agentId: 'agent-1', file_path: 'x' })
  expect(agent.context ?? []).toEqual([])
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

// A reload mid-compaction leaves the old ticker's status line behind; the next load clears it, or
// picks the count back up while the compaction is still running.
test('a reload clears a frozen compaction status, or resumes a running one', async ($: any, on) => {
  const clock = mock.clock(on, { now: 10_000_000 })
  for (const ev of ['ui.toast', 'ui.invalidate'] as const) on(ev, async () => ({ value: undefined }) as never)
  on('session.start', async (_$, e: any) => ({ cwd: e.cwd }) as never)
  const status: (string | undefined)[] = []
  on('ui.status', async (_$, e: any) => { status.push(e.text); return { value: undefined } as never })
  on('prompt.submit', async () => ({}) as never)
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

  // Once it ends the line clears as before. (The branch for a flag whose clean-up never ran, older
  // than STALE_COMPACTION, is not covered: a held compaction is cut off after 10 real seconds.)
  finish()
  await done
  await clock.advance(1000)
  expect(status.at(-1)).toBeUndefined()
})
