import { expect, mock, test } from 'claude-code/testing'
import { RED, TRICKS } from './band'

// The terminal writes `used / pace` in one run; the desktop raises the pace in a smaller grey run
// of its own. Resolves to the used figure's node, and only when the pace sits beside it.
const paced = async (ui: any, surface: string, used: string, pace: string) => {
  if (surface === 'terminal') return ui.find({ text: new RegExp(`^${used} / ${pace}$`) })
  const sup = await ui.find({ text: new RegExp(`^ / ${pace}$`) })
  return sup?.props.size === 'caption' && sup.props.dimColor ? ui.find({ text: new RegExp(`^${used}$`) }) : undefined
}

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
    expect(await ui.find({ text: /^–$/ })).toBeDefined()
    if (surface === 'desktop') expect(await ui.find({ text: /^Unknown until the next reply$/ })).toBeDefined()
    // Used, then the pace: one hour left of five, so 80% (owner, 2026-10-04).
    expect(await paced(ui, surface, '40%', '80%')).toBeDefined()
  })

  // After a compaction the local estimate stands in, marked as one, until the next reply (owner, 2026-10-27).
  test(`${surface}: the band shows the estimate before the first context figure`, async ($: any, on) => {
    mock.clock(on, { now: 1_000_000 })
    on('session.usage', async (_$, e: any) => ({ value: { startedAt: 0, rateLimits: [], context: { window: 330_000,
      ...(e?.breakdown === 'summary' ? { breakdown: { totalTokens: 99_000 } } : {}) } } }) as never)
    on('settings.read', async () => ({ value: {} }) as never)
    on('store.get', async () => ({ value: undefined }) as never)
    const ui = await $.ui.mount({ plugin: 'asdev', surface, component: 'AbovePrompt', props: { hasSurvey: false } })
    expect(await ui.find({ text: /^~30%$/ })).toBeDefined()
    if (surface === 'desktop') {
      expect(await ui.find({ text: /estimated until the next reply/ })).toBeDefined()
      // A ring the cache ring's size, with no label before it (owner, 2026-10-27).
      const svg = await ui.find({ type: 'Svg' })
      expect(svg?.props).toMatchObject({ alt: expect.stringMatching(/^Context: ~30%/), width: 18 })
      // Only its hover card names it.
      expect((await ui.findAll({ type: 'Text' })).filter((t: any) => t.text === 'Context').length).toBe(1)
      // A Box's width is in cells: a figure's box is a few of them, never a pixel count.
      const fixed = (await ui.findAll({ type: 'Box' })).map((b: any) => b.props.width).filter((w: any) => typeof w === 'number')
      expect(fixed.length).toBeGreaterThan(0)
      expect(Math.max(...fixed)).toBeLessThanOrEqual(12)
    }
  })

  // A limit used faster than its window passes turns its figure, and on the desktop its arrow, red.
  // A side panel narrows the band; the bars share what is left, between 24 and 112 px (owner, 2026-10-27).
  if (surface === 'desktop') test('desktop: the bars narrow with the band, within their bounds', async ($: any, on) => {
    mock.clock(on, { now: 1_000_000 })
    const resetsAt = new Date(1_000_000 + 3600_000).toISOString()
    on('session.usage', async () => ({ value: { startedAt: 0, rateLimits: [{ kind: 'five_hour', percentUsed: 10, resetsAt }, { kind: 'seven_day', percentUsed: 10, resetsAt }], context: { window: 330_000 } } }) as never)
    on('settings.read', async () => ({ value: {} }) as never)
    on('store.get', async () => ({ value: undefined }) as never)
    const widths = async (columns?: number) => {
      const ui = await $.ui.mount({ plugin: 'asdev', surface, component: 'AbovePrompt', props: { hasSurvey: false },
        ...(columns ? { viewport: { columns, rows: 40 } } : {}) })
      const w = (await ui.findAll({ type: 'Svg' })).filter((s: any) => /^(5 hours|Week)/.test(s.props.alt)).map((s: any) => s.props.width)
      await ui.unmount()
      return w
    }
    expect(await widths()).toEqual([112, 112])
    expect(await widths(200)).toEqual([112, 112])
    const mid = await widths(80)
    expect(mid[0]).toBe(mid[1])
    expect(mid[0]).toBeGreaterThan(24)
    expect(mid[0]).toBeLessThan(112)
    expect(await widths(30)).toEqual([24, 24])
  })

  // With the bars at their narrowest, the cost goes first, then the cache ring (owner, 2026-10-27).
  if (surface === 'desktop') test('desktop: a narrow band drops the cost, then the cache ring', async ($: any, on) => {
    mock.clock(on, { now: 1_000_000 })
    const resetsAt = new Date(1_000_000 + 3600_000).toISOString()
    on('session.usage', async () => ({ value: { startedAt: 0, cost: { usd: 3.73 }, context: { tokens: 50_000, window: 330_000 },
      rateLimits: [{ kind: 'five_hour', percentUsed: 10, resetsAt }, { kind: 'seven_day', percentUsed: 10, resetsAt }] } }) as never)
    on('settings.read', async () => ({ value: {} }) as never)
    on('store.get', async () => ({ value: undefined }) as never)
    on('turn.step', async function* (_$, e) {
      const usage = { input_tokens: 1000, output_tokens: 10, cache_read_input_tokens: 0, cache_creation_input_tokens: 0, model: 'm' }
      return { turnId: e.turnId, index: e.index, answer: '', toolUses: [], stopReason: 'end_turn', usage } as never
    })
    const s = $.turn.step({ turnId: 't', index: 0, model: 'm', messageCount: 1 })
    if (s && typeof s[Symbol.asyncIterator] === 'function') { for await (const _ of s) { /* drain */ } } else await s
    const shown = async (columns: number) => {
      const ui = await $.ui.mount({ plugin: 'asdev', surface, component: 'AbovePrompt', props: { hasSurvey: false }, viewport: { columns, rows: 40 } })
      const got = { cost: !!(await ui.find({ text: '$3.73' })), cache: (await ui.findAll({ type: 'Svg' })).some((v: any) => /^Prompt cache/.test(v.props.alt)) }
      await ui.unmount()
      return got
    }
    expect(await shown(120)).toEqual({ cost: true, cache: true })
    const steps = [] as { cost: boolean; cache: boolean }[]
    for (let c = 120; c >= 40; c -= 2) steps.push(await shown(c))
    // Never the cache ring without the cost's going first, and both gone at the narrowest.
    expect(steps.some(x => !x.cost && x.cache)).toBe(true)
    expect(steps.every(x => x.cost ? x.cache : true)).toBe(true)
    expect(steps.at(-1)).toEqual({ cost: false, cache: false })
  })

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
    on('session.usage', async () => ({ value: { startedAt: 0, rateLimits: [], context: { window: 330_000 } } }) as never)
    on('settings.read', async () => ({ value: {} }) as never)
    on('store.get', async () => ({ value: [{ kind: 'five_hour', percentUsed: 40, resetsAt }, { kind: 'seven_day', percentUsed: 90, resetsAt: resetAlready }] }) as never)
    const ui = await $.ui.mount({ plugin: 'asdev', surface, component: 'AbovePrompt', props: { hasSurvey: false } })
    // Used, then the pace: one hour left of five, so 80% (owner, 2026-10-04).
    expect(await paced(ui, surface, '40%', '80%')).toBeDefined()
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
    expect(await paced(ui, surface, '40%', '80%')).toBeDefined()
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

  // After the move to Enterprise the session reports no 5-hour or week window: once it has replied,
  // the kept Team figures go rather than standing in until their reset.
  test(`${surface}: kept limits the session no longer reports go`, async ($: any, on) => {
    mock.clock(on, { now: 1_000_000 })
    const resetsAt = new Date(1_000_000 + 3600_000).toISOString()
    on('session.usage', async () => ({ value: { startedAt: 0, rateLimits: [], context: { tokens: 50_000, window: 330_000 } } }) as never)
    on('settings.read', async () => ({ value: {} }) as never)
    on('store.get', async () => ({ value: [{ kind: 'five_hour', percentUsed: 40, resetsAt }, { kind: 'seven_day', percentUsed: 90, resetsAt }] }) as never)
    const ui = await $.ui.mount({ plugin: 'asdev', surface, component: 'AbovePrompt', props: { hasSurvey: false } })
    expect(await ui.find({ text: /40%|90%/ })).toBeUndefined()
    expect(await ui.find({ text: /^(5h|5 hours|Week)\b/ })).toBeUndefined()
  })

  // A monthly quota is a Month row paced over the calendar month that ends at its reset; a kept Team
  // window the session does not report goes.
  test(`${surface}: a monthly limit is a Month row with its pace`, async ($: any, on) => {
    mock.clock(on, { now: Date.UTC(2026, 9, 21) })
    // 20 of October's 31 days gone: a pace of 65%.
    const resetsAt = new Date(Date.UTC(2026, 10, 1)).toISOString()
    on('session.usage', async () => ({ value: { startedAt: 0, rateLimits: [{ kind: 'spend_limit', percentUsed: 40, resetsAt }], context: { tokens: 50_000, window: 330_000 } } }) as never)
    on('settings.read', async () => ({ value: {} }) as never)
    on('store.get', async () => ({ value: [{ kind: 'five_hour', percentUsed: 77, resetsAt }] }) as never)
    const ui = await $.ui.mount({ plugin: 'asdev', surface, component: 'AbovePrompt', props: { hasSurvey: false } })
    expect(await ui.find({ text: /^Month\b/ })).toBeDefined()
    expect(await paced(ui, surface, '40%', '65%')).toBeDefined()
    expect(await ui.find({ text: /77%/ })).toBeUndefined()

    await ui.press({ key: 'hide' })
    const foot = await $.ui.mount({ plugin: 'asdev', surface, component: 'SessionMode', props: { modes: [] } })
    if (surface === 'terminal') expect(await foot.find({ text: /^██░░$/ })).toBeDefined()
    else {
      const svg = (await foot.find({ type: 'Svg' }))?.props
      expect(svg?.alt).toBe('Month 40%')
      // One bar, in the middle.
      expect(svg?.source.match(/<rect y="[^"]+" width="28"/g)).toEqual(['<rect y="3.5" width="28"'])
    }
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
    // Hovering a meter opens a card explaining it; hidden until then, and inside
    // the meter's keyed Box, so the pointer on the meter is what reveals it.
    if (surface === 'desktop') {
      // find() leaves out `hover`; the drawn tree keeps it.
      const byKey = (n: any, key: string): any => n?.props?.key === key ? n
        : (n?.children ?? []).reduce((hit: any, c: any) => hit ?? byKey(c, key), undefined)
      const strip = byKey(await ui.drawn(), 'Context')?.children.find((c: any) => c.props?.display === 'none')
      expect(strip?.props).toMatchObject({ position: 'absolute', display: 'none' })
      expect(strip?.hover).toMatchObject({ display: 'flex' })
      // One point per line, so a narrow card does not squeeze them into one.
      expect(await ui.find({ text: /^50k of 330k tokens used$/ })).toBeDefined()
      // The band itself shows the share, to stay on one row.
      expect(await ui.find({ text: new RegExp(`^${Math.round(50 / 330 * 100)}%$`) })).toBeDefined()
      // Each line starts with a capital; the explanation after the figure is dimmed.
      expect((await ui.find({ text: /^First gap/ }))?.props.dimColor).toBe(true)
      // Three sections split where it compacts; the fill, in the first one's green, stops at its gap.
      const source = (await ui.findAll({ type: 'Svg' })).find((s: any) => /^Context/.test(s.props.alt))?.props.source ?? ''
      expect(['#8884', '#e0b02a55', '#d9534f55'].every(c => source.includes(`stroke="${c}"`))).toBe(true)
      expect(source.match(/<circle/g)?.length).toBe(4)
      expect(source).toContain('stroke="#2e9e6a"')
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
    expect(shown?.props).toMatchObject({ width: 620, height: 24 })
    expect(shown?.props.isInteractive).toBeUndefined()
    // Over the meters he would catch the pointer and hide their cards: on the band he steps away.
    expect((await ui.find({ type: 'Box', hover: { top: -240 } }))).toBeDefined()

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

// The kept limits follow the account: an empty list is kept too, and a reply with no windows clears
// them even when the list never changed in this session. The kinds that arrive are recorded.
test('the kept limits follow what the session reports', async ($: any, on) => {
  mock.clock(on, { now: Date.UTC(2026, 9, 21) })
  const store: Record<string, unknown> = { limits: [{ kind: 'five_hour', percentUsed: 40 }], kindsSeen: { five_hour: 'earlier' } }
  on('store.get', async (_$, e) => ({ value: store[e.key] }) as never)
  on('store.set', async (_$, e) => { store[e.key] = e.value; return { value: undefined } as never })
  on('ui.invalidate', async () => ({ value: undefined }) as never)
  on('session.measure', async (_$, e) => ({ changed: e.changed }) as never)
  const context = { tokens: 50_000, window: 330_000 }

  await $.session.measure({ context, rateLimits: [{ kind: 'spend_limit', percentUsed: 5 }], changed: ['rateLimits'] })
  expect(store.limits).toEqual([{ kind: 'spend_limit', percentUsed: 5 }])
  expect(store.kindsSeen).toEqual({ five_hour: 'earlier', spend_limit: '2026-10-21T00:00:00.000Z' })

  await $.session.measure({ context, rateLimits: [], changed: ['rateLimits'] })
  expect(store.limits).toEqual([])

  store.limits = [{ kind: 'five_hour', percentUsed: 40 }]
  await $.session.measure({ context: { window: 330_000 }, rateLimits: [], changed: ['context'] })
  expect(store.limits).toHaveLength(1)
  await $.session.measure({ context, rateLimits: [], changed: ['context'] })
  expect(store.limits).toEqual([])
})

// The usage endpoint's account figure, in cents.
const usageBody = (used: number, limit = 150_000, enabled = true) =>
  JSON.stringify({ extra_usage: { is_enabled: enabled, monthly_limit: limit, used_credits: used, currency: 'USD' } })
const accountMocks = (on: any, store: Record<string, unknown>) => {
  on('store.get', async (_$: any, e: any) => ({ value: store[e.key] }) as never)
  on('store.set', async (_$: any, e: any) => { store[e.key] = e.value; return { value: undefined } as never })
  on('ui.invalidate', async () => ({ value: undefined }) as never)
  on('session.measure', async (_$: any, e: any) => ({ changed: e.changed }) as never)
}
const measured = async ($: any, clock: any) => {
  await $.session.measure({ context: { tokens: 50_000, window: 330_000 }, rateLimits: [], changed: ['context'] })
  await clock.settle()
}

// A measure reads the account figure at most every 2 minutes, into dollars, and keeps the day's first
// figure; a fall (a new month's reset) starts the day again.
test('the account figure is read into the store', async ($: any, on) => {
  const now = new Date(2026, 9, 21, 12).getTime()
  const clock = mock.clock(on, { now })
  const store: Record<string, unknown> = {}
  const calls: any[] = []
  let used = 41_200
  accountMocks(on, store)
  on('session.authorize', async () => ({ value: { handle: 'h1', kind: 'bearer' } }) as never)
  on('http.fetch', async (_$, e) => { calls.push(e); return { value: { status: 200, ok: true, headers: {}, text: usageBody(used) } } as never })

  await measured($, clock)
  expect(calls).toHaveLength(1)
  expect(calls[0]).toMatchObject({ url: 'https://api.anthropic.com/api/oauth/usage', init: { headers: { 'anthropic-beta': 'oauth-2025-04-20' }, auth: 'h1' } })
  expect(store.month).toEqual({ used: 412, limit: 1500, at: now, currency: 'USD' })
  expect(store.monthStatus).toBe('ok')
  expect(store.dayStart).toEqual({ day: '2026-10-21', used: 412 })

  used = 45_000
  await clock.advance(90_000)
  await measured($, clock)
  expect(calls).toHaveLength(1)
  await clock.advance(60_000)
  await measured($, clock)
  expect(calls).toHaveLength(2)
  expect(store.month).toMatchObject({ used: 450 })
  expect(store.dayStart).toEqual({ day: '2026-10-21', used: 412 })

  used = 1_000
  await clock.advance(6 * 60_000)
  await measured($, clock)
  expect(store.dayStart).toEqual({ day: '2026-10-21', used: 10 })

  used = 2_000
  await clock.advance(24 * 3600_000)
  await measured($, clock)
  expect(store.dayStart).toEqual({ day: '2026-10-22', used: 20 })

  // A try stamped ahead of now (a clock since moved back) must not stop the reads until it catches up.
  store.monthTry = Number(store.monthTry) + 3600_000
  await measured($, clock)
  expect(calls).toHaveLength(5)
})

// Anything but a good figure stores none, so no row shows, and says why. A session without the
// account's login leaves the figure and the 5-minute slot as they were, and never sends an API key.
test('a failed read stores no figure', async ($: any, on) => {
  const clock = mock.clock(on, { now: new Date(2026, 9, 21, 12).getTime() })
  const store: Record<string, unknown> = {}
  let auth: unknown, res: unknown, fetched = 0
  accountMocks(on, store)
  on('session.authorize', async () => ({ value: auth }) as never)
  on('http.fetch', async () => { fetched++; return { value: res } as never })
  const bearer = { handle: 'h1', kind: 'bearer' }
  const reply = (text: string, status = 200) => ({ status, ok: status < 300, headers: {}, text })
  const cases: [unknown, unknown, RegExp][] = [
    [null, undefined, /^no credential$/],
    [{ handle: 'k1', kind: 'api-key' }, undefined, /^api-key$/],
    [bearer, reply('', 500), /^500$/],
    [bearer, reply(usageBody(100, 150_000, false)), /^not enabled$/],
    [bearer, reply('{}'), /^no extra_usage$/],
    [bearer, reply(usageBody(100, 0)), /^bad figures$/],
    [bearer, reply('not json'), /^error: /],
    // Number(null) is 0: a day started there would count the month's spend as today's.
    [bearer, reply(JSON.stringify({ extra_usage: { is_enabled: true, monthly_limit: 150_000, used_credits: null } })), /^bad figures$/],
  ]
  for (const [a, r, why] of cases) {
    auth = a
    res = r
    const kept = { used: 1, limit: 2, at: 0, currency: 'USD' }
    store.month = kept
    await clock.advance(6 * 60_000)
    await measured($, clock)
    const own = (a as { kind?: string } | null)?.kind === 'bearer'
    expect(store.month).toEqual(own ? null : kept)
    if (!own) expect(store.monthTry).toBeUndefined()
    expect(store.monthStatus).toMatch(why)
  }
  expect(fetched).toBe(6)
})

// With no replies, the open band reads the figure again once it is 12 hours old, and not before.
test('an idle band reads the figure every 12 hours', async ($: any, on) => {
  const clock = mock.clock(on, { now: new Date(2026, 9, 21, 12).getTime() })
  const store: Record<string, unknown> = {}
  let fetched = 0
  accountMocks(on, store)
  on('session.usage', async () => ({ value: { startedAt: 0, rateLimits: [], context: { tokens: 50_000, window: 330_000 } } }) as never)
  on('session.authorize', async () => ({ value: { handle: 'h1', kind: 'bearer' } }) as never)
  on('http.fetch', async () => { fetched++; return { value: { status: 200, ok: true, headers: {}, text: usageBody(100) } } as never })
  await $.ui.mount({ plugin: 'asdev', surface: 'desktop', component: 'AbovePrompt', props: { hasSurvey: false } })
  await measured($, clock)
  expect(fetched).toBe(1)
  await clock.advance(11 * 3600_000)
  await clock.settle()
  expect(fetched).toBe(1)
  await clock.advance(3600_000)
  await clock.settle()
  expect(fetched).toBe(2)
})

// A read that never answers gives up after 10 s, so it cannot block every later read.
test('a hung read times out', async ($: any, on) => {
  const clock = mock.clock(on, { now: new Date(2026, 9, 21, 12).getTime() })
  const store: Record<string, unknown> = {}
  let fetched = 0
  accountMocks(on, store)
  on('session.authorize', async () => ({ value: { handle: 'h1', kind: 'bearer' } }) as never)
  on('http.fetch', async () => { fetched++; await new Promise(() => {}); return { value: undefined } as never })
  await measured($, clock)
  await clock.advance(10_000)
  expect(store.monthStatus).toBe('timeout')
  await clock.advance(5 * 60_000)
  await measured($, clock)
  expect(fetched).toBe(2)
})

// A read stuck before its fetch (here the sign-in step) stops blocking the next after 30 s.
test('a stuck read stops blocking the next', async ($: any, on) => {
  const clock = mock.clock(on, { now: new Date(2026, 9, 21, 12).getTime() })
  const store: Record<string, unknown> = {}
  let asked = 0, fetched = 0
  accountMocks(on, store)
  on('session.authorize', async () => { if (!asked++) await new Promise(() => {}); return { value: { handle: 'h1', kind: 'bearer' } } as never })
  on('http.fetch', async () => { fetched++; return { value: { status: 200, ok: true, headers: {}, text: usageBody(100) } } as never })
  await measured($, clock)
  await clock.advance(10_000)
  await measured($, clock)
  expect(fetched).toBe(0)
  await clock.advance(30_000)
  await measured($, clock)
  expect(fetched).toBe(1)
})

// The account figure is a Today and a Month row after Context. Today's allowance is 95% of what the
// month had left this morning over the working days left, today included.
for (const surface of ['terminal', 'desktop'] as const) {
  const wed = new Date(2026, 9, 21, 12).getTime()
  const mount = async ($: any, on: any, now: number, start: number, extra: Record<string, unknown> = {}, limits: unknown[] = []) => {
    mock.clock(on, { now })
    const resetsAt = new Date(2026, 10, 1).toISOString()
    on('session.usage', async () => ({ value: { startedAt: 0, rateLimits: [{ kind: 'spend_limit', percentUsed: 40, resetsAt }, ...limits], context: { tokens: 50_000, window: 330_000 } } }) as never)
    on('settings.read', async () => ({ value: {} }) as never)
    const d = new Date(now)
    const store: Record<string, unknown> = {
      month: { used: 412, limit: 1500, at: now - 60_000, currency: 'USD' },
      dayStart: { day: `2026-10-${String(d.getDate()).padStart(2, '0')}`, used: start },
      ...extra,
    }
    on('store.get', async (_$: any, e: any) => ({ value: store[e.key] }) as never)
    return $.ui.mount({ plugin: 'asdev', surface, component: 'AbovePrompt', props: { hasSurvey: false } })
  }
  const lit = (s: string) => s.replace(/\$/g, '\\$')
  // The desktop shows the share beside the bar and the dollars in its hover card; the terminal, with
  // no hover card, writes the dollars.
  const row = async (ui: any, spent: string, of: string, share: string) => surface === 'terminal'
    ? ui.find({ text: new RegExp(`^${lit(spent)} of ${lit(of)}$`) })
    : paced(ui, surface, ...share.split(' / ') as [string, string])

  test(`${surface}: the account figure is a Today and a Month row`, async ($: any, on) => {
    // $1,100 left this morning over 8 working days: $131 allowed, $12 spent.
    const ui = await mount($, on, wed, 400)
    const today = await row(ui, '$12', '$131', '9% / 50%')
    expect(today).toBeDefined()
    expect(today?.props.color).not.toBe(RED)
    // Noon on the 21st: 20.5 of October's 31 days gone, a 66% pace.
    expect(await row(ui, '$412', '$1,500', '27% / 66%')).toBeDefined()
    if (surface !== 'terminal') expect(await ui.find({ text: /^(of )?\$[\d,]+$/ })).toBeUndefined()
    const names = (await ui.findAll({ type: 'Text' })).map((t: any) => /^(Context|Today|Month)\b/.exec(t.text)?.[1]).filter(Boolean)
    // The desktop names each row twice, its label and its hover card.
    expect([...new Set(names)]).toEqual(['Context', 'Today', 'Month'])
    // The monthly window would count the month twice.
    expect(await ui.find({ text: /40%/ })).toBeUndefined()
  })

  test(`${surface}: Today turns red past its allowance`, async ($: any, on) => {
    // $1,300 left over 8 days: $154 allowed, $212 spent.
    const ui = await mount($, on, wed, 200)
    expect((await row(ui, '$212', '$154', '137% / 50%'))?.props.color).toBe(RED)
  })

  test(`${surface}: a weekend shows the next working day's allowance`, async ($: any, on) => {
    // Saturday the 24th: 5 working days left, $1,100 over them.
    const ui = await mount($, on, new Date(2026, 9, 24, 12).getTime(), 400)
    expect(await row(ui, '$12', '$209', '6% / 50%')).toBeDefined()
  })

  test(`${surface}: a weekend that ends the month shows the next month's share`, async ($: any, on) => {
    // Saturday the 31st: none left, so $1,500 over November's 21 working days.
    const ui = await mount($, on, new Date(2026, 9, 31, 12).getTime(), 400)
    expect(await row(ui, '$12', '$68', '18% / 50%')).toBeDefined()
  })

  // 07:00 is before the working day, 18:00 after it: the pace holds at 0% and 100%.
  for (const [hour, pace] of [[7, '0%'], [18, '100%']] as const) {
    test(`${surface}: Today's pace at ${hour}:00 is ${pace}, the working hours only`, async ($: any, on) => {
      const ui = await mount($, on, new Date(2026, 9, 21, hour).getTime(), 400)
      expect(await row(ui, '$12', '$131', `9% / ${pace}`)).toBeDefined()
    })
  }

  test(`${surface}: no figure yet today counts nothing spent today`, async ($: any, on) => {
    // Yesterday's first figure must not count yesterday's spend: today starts at $412, so $1,088 over 8 days.
    const ui = await mount($, on, wed, 400, { dayStart: { day: '2026-10-20', used: 100 } })
    expect(await row(ui, '$0', '$129', '0% / 50%')).toBeDefined()
  })

  const stale: [string, unknown][] = [
    ['from an earlier month', { used: 412, limit: 1500, at: new Date(2026, 8, 30, 12).getTime(), currency: 'USD' }],
    ['of the wrong shape', { used: '412', limit: 1500, at: wed, currency: 'USD' }],
  ]
  for (const [what, month] of stale) {
    test(`${surface}: a figure ${what} shows no row, and the monthly window stays`, async ($: any, on) => {
      const ui = await mount($, on, wed, 400, { month })
      expect(await ui.find({ text: /^Today\b/ })).toBeUndefined()
      expect(await ui.find({ text: /40%/ })).toBeDefined()
    })
  }

  test(`${surface}: the collapsed band shows Today and Month`, async ($: any, on) => {
    const band = await mount($, on, wed, 400)
    await band.press({ key: 'hide' })
    const foot = await $.ui.mount({ plugin: 'asdev', surface, component: 'SessionMode', props: { modes: [] } })
    if (surface === 'terminal') expect(await foot.find({ text: /^░░░░ █░░░$/ })).toBeDefined()
    else expect((await foot.find({ type: 'Svg' }))?.props.alt).toBe('Today 9%, month 27%')
  })

  test(`${surface}: the collapsed band puts a usage window before the spend`, async ($: any, on) => {
    const band = await mount($, on, wed, 400, {}, [{ kind: 'five_hour', percentUsed: 50, resetsAt: new Date(2026, 9, 21, 15).toISOString() }])
    await band.press({ key: 'hide' })
    const foot = await $.ui.mount({ plugin: 'asdev', surface, component: 'SessionMode', props: { modes: [] } })
    if (surface === 'terminal') expect(await foot.find({ text: /^██░░ ░░░░$/ })).toBeDefined()
    else expect((await foot.find({ type: 'Svg' }))?.props.alt).toBe('5 hours 50%, today 9%')
  })
}
