import { expect, mock, test } from 'claude-code/testing'

// The test's hooks stand for the engine beneath the mod: brain.py's answer, the store, the files.
function world(on: any, answer: { out: unknown; fail?: boolean }) {
  const runs: string[][] = []
  const store: Record<string, unknown> = {}
  on('classic.SessionStart', async () => ({}) as never)
  on('store.get', async (_$: any, e: any) => ({ value: store[e.key] }) as never)
  on('store.set', async (_$: any, e: any) => { store[e.key] = e.value; return { value: undefined } as never })
  on('fs.exists', async () => ({ value: false }) as never)
  on('process.run', async (_$: any, e: any) => {
    const argv = (e.argv ?? e) as string[]
    runs.push([...argv])
    if (answer.fail) throw new Error('python is not installed')
    const out = typeof answer.out === 'string' ? answer.out : JSON.stringify(answer.out)
    return { value: { exitCode: 0, stdout: out, stderr: '' } } as never
  })
  // Only brain.py's runs; a compaction's notice may run the budget check.
  const brainRuns = () => runs.filter(a => a.join(' ').includes('brain.main'))
  return { brainRuns }
}

const BRAIN = '/p/.docs/brain'
const ok = (step: string, message = 'done') => ({ ok: true, warn: false, step, message })
const INDEX = '# Memory Index\n\n- [A trap](a-trap.md) — the hook\n'
const start = ($: any, source: string) => $.classic.SessionStart({ source, cwd: '/p' })
const told = (r: any) => (r.additionalContext ?? []).join('\n')

test('a start that sets the brain up says where notes go, adds the index once, and a compaction repeats the line', async ($: any, on) => {
  mock.clock(on)
  const w = world(on, { out: { passed: true, skipped: '', brain: BRAIN, steps: [ok('setting'), ok('verify')], newly_set: true, moved: 2, index: INDEX } })
  const r = await start($, 'startup')
  const text = told(r)
  expect(w.brainRuns().length).toBe(1)
  expect(w.brainRuns()[0]).toContain('/p')
  expect(text).toContain('write new notes to `.docs/brain/`')
  expect(text).toContain('2 note(s) from the old hidden memory folder')
  expect(text.split('- [A trap](a-trap.md)').length - 1).toBe(1)
  expect((r.additionalContext ?? []).length).toBe(1)
  const after = told(await start($, 'compact'))
  expect(w.brainRuns().length).toBe(1)
  expect(after).toContain('write new notes to `.docs/brain/`')
  expect(after).not.toContain('a-trap.md')
})

test('a start with nothing to do adds nothing, and neither does a compaction in a session that set nothing up', async ($: any, on) => {
  mock.clock(on)
  const w = world(on, { out: { passed: true, skipped: '', brain: BRAIN, steps: [ok('start')] } })
  expect(told(await start($, 'startup'))).toBe('')
  expect(told(await start($, 'resume'))).toBe('')
  expect(told(await start($, 'clear'))).toBe('')
  expect(w.brainRuns().length).toBe(3)
  expect(told(await start($, 'compact'))).not.toContain('.docs/brain/')
  expect(w.brainRuns().length).toBe(3)
})

test('a folder outside a repo with .docs/ keeps the harness default, told nothing', async ($: any, on) => {
  mock.clock(on)
  world(on, { out: { passed: false, skipped: '/x has no .docs/ folder', brain: '', steps: [] } })
  expect(told(await start($, 'startup'))).toBe('')
})

test('notes left in the old folder by an earlier session are moved in and named, the index with them', async ($: any, on) => {
  mock.clock(on)
  world(on, { out: { passed: true, skipped: '', brain: BRAIN, newly_set: false, moved: 1, index: INDEX,
    steps: [ok('setting'), { ok: true, warn: true, step: 'clash', message: 'a.md differs, so it arrived as a-migrated.md: merge the two' }] } })
  const text = told(await start($, 'startup'))
  expect(text).toContain('1 note(s) from the old hidden memory folder')
  expect(text).toContain('clash: a.md differs')
  expect(text).toContain('a-trap.md')
  // Set up in an earlier session: the harness already saves to the brain.
  expect(text).not.toContain('write new notes')
})

test('a refusal is told once per project, and again only once it changes', async ($: any, on) => {
  mock.clock(on)
  const answer = { out: { passed: false, skipped: '', brain: BRAIN, steps: [{ ok: false, warn: false, step: 'setting', message: 'already points at /elsewhere' }] } as any }
  world(on, answer)
  expect(told(await start($, 'startup'))).toContain('already points at /elsewhere')
  expect(told(await start($, 'startup'))).toBe('')
  answer.out = { ...answer.out, steps: [{ ok: false, warn: false, step: 'ignore', message: 'settings.local.json is committed' }] }
  expect(told(await start($, 'startup'))).toContain('settings.local.json is committed')
  expect(told(await start($, 'startup'))).toBe('')
})

test('a broken run never breaks the start', async ($: any, on) => {
  mock.clock(on)
  const answer = { out: 'Traceback (most recent call last):' as unknown, fail: false }
  world(on, answer)
  expect(told(await start($, 'startup'))).toBe('')
  answer.fail = true
  expect(told(await start($, 'startup'))).toBe('')
})
