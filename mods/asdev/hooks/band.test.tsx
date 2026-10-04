import { expect, mock, test } from 'claude-code/testing'
import { RED, TIP_BG, TRICKS } from './band'

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
    // On the desktop Clawd vacuums beside the timer; the terminal cannot animate a drawing.
    const vac = await ui.find({ type: 'Svg' })
    if (surface === 'terminal') expect(vac).toBeUndefined()
    // Sized, or the frame stands 150 px tall and the band with it (owner's screenshot, 2026-10-04).
    else expect(vac?.props).toMatchObject({ alt: 'Clawd vacuums up the old context', isInteractive: true, width: 300, height: 24 })

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
    // Used, then the pace: one hour left of five, so 80% (owner, 2026-10-04).
    expect(await ui.find({ text: /40% \/ 80%/ })).toBeDefined()
  })

  // A limit used faster than its window passes turns its figure, and on the desktop its arrow, red.
  test(`${surface}: a limit ahead of pace shows red`, async ($: any, on) => {
    mock.clock(on, { now: 1_000_000 })
    const resetsAt = new Date(1_000_000 + 3600_000).toISOString()
    // One hour left: the 5-hour pace is 80%, so 90% is ahead; the week's pace is near 100%, so 10% is not.
    on('session.usage', async () => ({ value: { startedAt: 0, rateLimits: [{ kind: 'five_hour', percentUsed: 90, resetsAt }, { kind: 'seven_day', percentUsed: 10, resetsAt }], context: { window: 330_000 } } }) as never)
    on('settings.read', async () => ({ value: {} }) as never)
    on('store.get', async () => ({ value: undefined }) as never)
    const ui = await $.ui.mount({ plugin: 'asdev', surface, component: 'AbovePrompt', props: { hasSurvey: false } })
    const red = (await ui.findAll({ type: 'Text' })).filter((t: any) => t.props.color === RED).map((t: any) => t.text).join('|')
    expect(red).toMatch(/90%/)
    expect(red).not.toMatch(/10%/)
    if (surface === 'desktop') {
      const svgs = await ui.findAll({ type: 'Svg' })
      const arrow = (alt: RegExp) => /<polygon[^>]*fill="([^"]+)"/.exec(svgs.find((s: any) => alt.test(s.props.alt))?.props.source ?? '')?.[1]
      expect(arrow(/^5 hours/)).toBe(RED)
      expect(arrow(/^Week/)).not.toBe(RED)
    }
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
    // Used, then the pace: one hour left of five, so 80% (owner, 2026-10-04).
    expect(await ui.find({ text: /40% \/ 80%/ })).toBeDefined()
    expect(await ui.find({ text: /90%/ })).toBeUndefined()
  })

  // A chat left idle keeps the reading of its last reply; the newest any session saw wins.
  test(`${surface}: the newest limits win over the session's own`, async ($: any, on) => {
    mock.clock(on, { now: 1_000_000 })
    const resetsAt = new Date(1_000_000 + 3600_000).toISOString()
    on('session.usage', async () => ({ value: { startedAt: 0, rateLimits: [{ kind: 'five_hour', percentUsed: 20, resetsAt }], context: { tokens: 50_000, window: 330_000 } } }) as never)
    on('settings.read', async () => ({ value: {} }) as never)
    on('store.get', async () => ({ value: [{ kind: 'five_hour', percentUsed: 40, resetsAt }] }) as never)
    const ui = await $.ui.mount({ plugin: 'asdev', surface, component: 'AbovePrompt', props: { hasSurvey: false } })
    expect(await ui.find({ text: /40% \/ 80%/ })).toBeDefined()
    expect(await ui.find({ text: /20%/ })).toBeUndefined()
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
    else expect((await foot.find({ type: 'Svg' }))?.props.alt).toBe('5 hours 40%, week 75%')
  })

  // Clawd turns up on the desktop within a few minutes, does one of the tricks and leaves.
  test(`${surface}: Clawd does a trick now and then`, async ($: any, on) => {
    const clock = mock.clock(on, { now: 1_000_000 })
    on('session.usage', async () => ({ value: { startedAt: 0, rateLimits: [], context: { tokens: 50_000, window: 330_000 } } }) as never)
    on('settings.read', async () => ({ value: {} }) as never)
    on('store.get', async () => ({ value: undefined }) as never)
    const tricks = Object.values(TRICKS).map(t => t.alt)
    const find = async (ui: any) => (await ui.find({ key: 'clawd' }))?.children[0]
    const ui = await $.ui.mount({ plugin: 'asdev', surface, component: 'AbovePrompt', props: { hasSurvey: false } })
    expect(await find(ui)).toBeUndefined()
    // Hovering a meter lays a dark strip over the band explaining it; hidden until then, and inside
    // the meter's keyed Box, so the pointer on the meter is what reveals it.
    if (surface === 'desktop') {
      // find() leaves out `hover`; the drawn tree keeps it.
      const byKey = (n: any, key: string): any => n?.props?.key === key ? n
        : (n?.children ?? []).reduce((hit: any, c: any) => hit ?? byKey(c, key), undefined)
      const strip = byKey(await ui.drawn(), 'Context')?.children.find((c: any) => c.props?.display === 'none')
      expect(strip?.props).toMatchObject({ position: 'absolute', display: 'none', backgroundColor: TIP_BG })
      expect(strip?.hover).toMatchObject({ display: 'flex' })
      expect(await ui.find({ text: /50k of 330k tokens used/ })).toBeDefined()
    }

    // The first comes at a random moment 2 to 6 minutes in; walk the clock until it shows.
    let shown
    for (let t = 0; t < 6 * 60 && !shown; t += 2) {
      await clock.advance(2000)
      await clock.settle()
      shown = await find(ui)
    }
    if (surface === 'terminal') { expect(shown).toBeUndefined(); return }
    expect(tricks).toContain(shown?.props.alt)
    expect(shown?.props).toMatchObject({ isInteractive: true, width: 620, height: 24 })

    await clock.advance(12_000)
    await clock.settle()
    expect(await find(ui)).toBeUndefined()
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
