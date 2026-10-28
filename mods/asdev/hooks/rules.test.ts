import { expect, mock, test } from 'claude-code/testing'
import type { On } from 'claude-code'
import { note, rules } from './rules'

const ROOT = 'C:/h/.claude/CLAUDE.md'
const MAIN = 'C:/h/.claude/setup/claude/CLAUDE.md'
const RULES = '# 1. Core\n- **Alpha.** Do a.\n- **Beta.** Do b,\n  on two lines.\n\n# 2. Git\n- **Gamma.** Do g.\n'

// The files the engine loaded, and the prompts that reached the session with what they carried.
function world(on: On, files: Record<string, string>) {
  const at: Record<string, number> = Object.fromEntries(Object.keys(files).map(p => [p, 1]))
  const size: { tokens?: number } = { tokens: 1000 }
  mock.clock(on)
  mock.env(on, { USERPROFILE: 'C:\\h' })
  on('session.usage', async () => ({ value: { startedAt: 0, rateLimits: [], context: { tokens: size.tokens, window: 1_000_000 } } }) as never)
  for (const ev of ['ui.toast', 'ui.status', 'ui.invalidate'] as const) on(ev, async () => ({ value: undefined }) as never)
  on('session.compact', async (_$, e) => ({ messages: e.messages }) as never)
  const path = (e: unknown) => String((e as any).path).replace(/\\/g, '/')
  on('fs.read', async (_$, e) => {
    const p = path(e)
    if (!(p in files)) throw new Error(`ENOENT ${p}`)
    return { value: files[p] } as never
  })
  on('fs.stat', async (_$, e) => {
    const p = path(e)
    if (!(p in files)) throw new Error(`ENOENT ${p}`)
    return { value: { kind: 'file', size: files[p].length, mtimeMs: at[p], isLink: false } } as never
  })
  const prompts: (readonly string[])[] = []
  on('prompt.submit', async (_$, e) => { prompts.push(e.context ?? []); return { text: e.text } as never })
  const edit = (p: string, text: string) => { files[p] = text; at[p]++ }
  return { prompts, edit, size }
}

const ask = ($: any) => $.prompt.submit({ text: 'go on' })

test('rules are keyed by section and bold lead-in, continuation lines kept', () => {
  const r = rules(RULES)
  expect([...r.keys()]).toEqual(['1. Core › Alpha.', '1. Core › Beta.', '2. Git › Gamma.'])
  expect(r.get('1. Core › Beta.')).toBe('- **Beta.** Do b,\n  on two lines.')
  expect([...rules('# S\n- plain rule one\n- plain rule one\n').keys()]).toEqual(['S › plain rule one', 'S › plain rule one (2)'])
})

test('the note names changed, added and removed rules and quotes the new text', () => {
  const after = RULES.replace('Do a.', 'Do a twice.').replace('- **Gamma.** Do g.\n', '- **Delta.** Do d.\n')
  const n = note(MAIN, RULES, after) ?? ''
  expect(n).toContain(`instructions in ${MAIN} changed`)
  expect(n).toContain('- changed: 1. Core › Alpha.')
  expect(n).toContain('- added: 2. Git › Delta.')
  expect(n).toContain('- removed: 2. Git › Gamma.')
  expect(n).toContain('- **Alpha.** Do a twice.')
  expect(n).toContain('- **Delta.** Do d.')
  expect(n).not.toContain('Do b')
  expect(n).toContain('A removed rule no longer applies.')
  expect(note(MAIN, RULES, RULES.replace(/\n/g, '\r\n'))).toBeUndefined()
})

test('past the cap the note lists names and asks for a read', () => {
  const big = RULES.replace('Do a.', `Do ${'a'.repeat(5000)}.`)
  const n = note(MAIN, RULES, big) ?? ''
  expect(n).toContain('- changed: 1. Core › Alpha.')
  expect(n).toContain('Read these rules from the file')
  expect(n).not.toContain('aaaa')
})

test('an edit to an imported file reaches the next prompt once', async ($: any, on) => {
  const w = world(on, { [ROOT]: '@~/.claude/setup/claude/CLAUDE.md\n', [MAIN]: RULES })
  await ask($)
  await ask($)
  expect(w.prompts).toEqual([[], []])
  w.edit(MAIN, RULES.replace('Do g.', 'Do g first.'))
  await ask($)
  expect(w.prompts[2].length).toBe(1)
  expect(w.prompts[2][0]).toContain('- changed: 2. Git › Gamma.')
  expect(w.prompts[2][0]).toContain('Do g first.')
  await ask($)
  expect(w.prompts[3]).toEqual([])
})

test('a save that changes no text carries no note', async ($: any, on) => {
  const w = world(on, { [ROOT]: '@~/.claude/setup/claude/CLAUDE.md\n', [MAIN]: RULES })
  await ask($)
  w.edit(MAIN, RULES)
  await ask($)
  expect(w.prompts[1]).toEqual([])
})

test('a compaction reloads the rules, so an earlier edit is no news after it', async ($: any, on) => {
  const w = world(on, { [ROOT]: '@~/.claude/setup/claude/CLAUDE.md\n', [MAIN]: RULES })
  await ask($)
  w.edit(MAIN, RULES.replace('Do a.', 'Do a now.'))
  await $.session.compact({ trigger: 'auto', messages: [{ role: 'user', text: 'hi', toolUses: [] }] })
  await ask($)
  expect(w.prompts[1]).toEqual([])
})

test('a reload keeps the baseline, so the first prompt after an edit carries the note', async ($: any, on) => {
  const w = world(on, { [ROOT]: '@~/.claude/setup/claude/CLAUDE.md\n', [MAIN]: RULES })
  on('session.start', async (_$, e: any) => ({ cwd: e.cwd }) as never)
  await ask($)
  w.edit(MAIN, RULES.replace('Do b,', 'Do b and c,'))
  await $.session.start({ cwd: '/p', surface: null, isInteractive: true })
  await ask($)
  expect(w.prompts[1][0]).toContain('- changed: 1. Core › Beta.')
  expect(w.prompts[1][0]).toContain('Do b and c,\n  on two lines.')
})

test('a missing CLAUDE.md never holds a prompt back', async ($: any, on) => {
  const w = world(on, {})
  await ask($)
  await ask($)
  expect(w.prompts).toEqual([[], []])
})
