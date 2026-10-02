import { expect, mock, test } from 'claude-code/testing'

// The app gives no sign of a compaction it did not start, so the band says so, collapsed or not.
for (const surface of ['terminal', 'desktop'] as const) {
  test(`${surface}: the band shows a running compaction`, async ($: any, on) => {
    const clock = mock.clock(on, { now: 1_000_000 })
    on('session.usage', async () => ({ value: { startedAt: 0, rateLimits: [], context: { tokens: 300_000, window: 1_000_000 } } }) as never)
    on('settings.read', async () => ({ value: {} }) as never)
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
    const ui = await $.ui.mount({ plugin: 'asdev', surface, component: 'AbovePrompt', props: { hasSurvey: false } })
    expect(await ui.find({ text: /– \/ 330k/})).toBeDefined()
    expect(await ui.find({ text: /40% · resets/ })).toBeDefined()
  })
}
