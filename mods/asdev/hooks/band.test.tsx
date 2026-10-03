import { expect, mock, test } from 'claude-code/testing'

// The app gives no sign of a compaction it did not start, so the band says so, collapsed or not.
for (const surface of ['terminal', 'desktop'] as const) {
  test(`${surface}: the band shows a running compaction`, async ($: any, on) => {
    const clock = mock.clock(on, { now: 1_000_000 })
    on('session.usage', async () => ({ value: { startedAt: 0, rateLimits: [], context: { tokens: 300_000, window: 1_000_000 } } }) as never)
    on('settings.read', async () => ({ value: {} }) as never)
    on('store.get', async () => ({ value: undefined }) as never)
    for (const ev of ['ui.toast', 'ui.status'] as const) on(ev, async () => ({ value: undefined }) as never)
    let finish = () => {}
    on('session.compact', async (_$, e) => { await new Promise<void>(r => { finish = r }); return { messages: e.messages } as never })

    const ui = await $.ui.mount({ plugin: 'asdev', surface, component: 'AbovePrompt', props: { hasSurvey: false } })
    expect(await ui.find({ text: /Compacting/ })).toBeUndefined()

    const done = $.session.compact({ trigger: 'auto', messages: [{ role: 'user', text: 'hi', toolUses: [] }] })
    await clock.advance(3000)
    expect((await ui.find({ text: /Compacting/ }))?.text).toContain('3 s')

    finish()
    await done
    await clock.settle()
    expect(await ui.find({ text: /Compacting/ })).toBeUndefined()
  })

  // A fresh session, or one just compacted or relaunched, has no context figure until its next reply.
  test(`${surface}: the band stays up before the first context figure`, async ($: any, on) => {
    mock.clock(on, { now: 1_000_000 })
    const resetsAt = new Date(1_000_000 + 3600_000).toISOString()
    on('session.usage', async () => ({ value: { startedAt: 0, rateLimits: [{ kind: 'five_hour', percentUsed: 40, resetsAt }], context: { window: 330_000 } } }) as never)
    on('settings.read', async () => ({ value: {} }) as never)
    on('store.get', async () => ({ value: undefined }) as never)
    const ui = await $.ui.mount({ plugin: 'asdev', surface, component: 'AbovePrompt', props: { hasSurvey: false } })
    expect(await ui.find({ text: /– \/ 330k/})).toBeDefined()
    expect(await ui.find({ text: surface === 'terminal' ? /40% · resets 1h/ : /40% · 1h/ })).toBeDefined()
  })

  // Before this session's first reply the last limits any session saw stand in, unless their window
  // has reset since. (The kit settles all work before a mount returns, so the waiting frame drawn
  // while the figures are slow cannot be observed here.)
  test(`${surface}: the kept limits stand in before the first reply`, async ($: any, on) => {
    mock.clock(on, { now: 1_000_000 })
    const resetsAt = new Date(1_000_000 + 3600_000).toISOString()
    const resetAlready = new Date(1_000_000 - 60_000).toISOString()
    on('session.usage', async () => ({ value: { startedAt: 0, rateLimits: [], context: { tokens: 50_000, window: 330_000 } } }) as never)
    on('settings.read', async () => ({ value: {} }) as never)
    on('store.get', async () => ({ value: [{ kind: 'five_hour', percentUsed: 40, resetsAt }, { kind: 'seven_day', percentUsed: 90, resetsAt: resetAlready }] }) as never)
    const ui = await $.ui.mount({ plugin: 'asdev', surface, component: 'AbovePrompt', props: { hasSurvey: false } })
    expect(await ui.find({ text: surface === 'terminal' ? /40% · resets 1h/ : /40% · 1h/ })).toBeDefined()
    expect(await ui.find({ text: /90%/ })).toBeUndefined()
  })

  // Collapsed, the band is two small bars beside the footer's modes, not a word.
  test(`${surface}: the collapsed band shows the limits`, async ($: any, on) => {
    mock.clock(on, { now: 1_000_000 })
    const resetsAt = new Date(1_000_000 + 3600_000).toISOString()
    on('session.usage', async () => ({ value: { startedAt: 0, rateLimits: [{ kind: 'five_hour', percentUsed: 40, resetsAt }, { kind: 'seven_day', percentUsed: 75, resetsAt }], context: { window: 330_000 } } }) as never)
    on('settings.read', async () => ({ value: {} }) as never)
    on('store.get', async () => ({ value: undefined }) as never)
    const band = await $.ui.mount({ plugin: 'asdev', surface, component: 'AbovePrompt', props: { hasSurvey: false } })
    await band.press({ key: 'hide' })
    const foot = await $.ui.mount({ plugin: 'asdev', surface, component: 'SessionMode', props: { modes: [] } })
    expect(await foot.find({ text: /Usage/ })).toBeUndefined()
    if (surface === 'terminal') expect(await foot.find({ text: /██░░ ███░/ })).toBeDefined()
    else expect(await foot.find({ alt: '5 hours 40%, week 75%' })).toBeDefined()
  })

  // The cache timer counts down from the last main-thread reply and turns red in its last ten minutes.
  test(`${surface}: the cache timer counts down from the last reply`, async ($: any, on) => {
    const clock = mock.clock(on, { now: 1_000_000 })
    on('session.usage', async () => ({ value: { startedAt: 0, rateLimits: [], context: { tokens: 50_000, window: 330_000 } } }) as never)
    on('settings.read', async () => ({ value: {} }) as never)
    on('store.get', async () => ({ value: undefined }) as never)
    // A main-thread reply, as compaction.ts sees it; a subagent's leaves the timer alone.
    on('turn.step', async function* (_$, e) {
      const usage = { input_tokens: 1000, output_tokens: 10, cache_read_input_tokens: 0, cache_creation_input_tokens: 0, model: 'm' }
      return { turnId: e.turnId, index: e.index, answer: '', toolUses: [], stopReason: 'end_turn', usage } as never
    })
    const ui = await $.ui.mount({ plugin: 'asdev', surface, component: 'AbovePrompt', props: { hasSurvey: false } })
    expect(await ui.find({ text: /cache|Cache/ })).toBeUndefined()

    const step = async (agentId?: string) => {
      const s = $.turn.step({ turnId: 't', index: 0, model: 'm', messageCount: 1, agentId })
      if (s && typeof s[Symbol.asyncIterator] === 'function') { for await (const _ of s) { /* drain */ } } else await s
    }
    await step()
    await clock.advance(18 * 60_000)
    await step('agent-1')
    await clock.settle()
    const fresh = await ui.find({ type: 'Text', text: /42m$/ })
    expect(fresh?.props.color).toBe('#2e9e6a')

    await clock.advance(38 * 60_000)
    await clock.settle()
    expect((await ui.find({ type: 'Text', text: /\b4m$/ }))?.props.color).toBe('#d9534f')

    await clock.advance(10 * 60_000)
    await clock.settle()
    expect(await ui.find({ text: /expired/ })).toBeDefined()
  })
}
