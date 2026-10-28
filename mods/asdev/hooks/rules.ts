import { atom, read, update } from 'claude-code'
import type { EngineInterface as Engine, Register } from 'claude-code'

// A session keeps the global instructions it loaded at its start (or last compaction): a rule edited
// meanwhile reaches it only after the next compaction. So the next prompt carries a note naming what
// changed, with the new text (work setup 2026-10-21, back-ported 2026-10-28).

type Seen = Record<string, { mtimeMs: number; text: string }>
const seen = atom({ plugin: 'asdev', key: 'rules' } as const, {} as Seen)
// Past this the note names the changed rules and asks for a read instead of quoting them.
const QUOTE_CAP = 4000
const LIST_CAP = 12

const ABS = /^([A-Za-z]:|[\\/])/

// The user's CLAUDE.md and the files it imports (`@path` lines), each as the engine loads it.
async function watched($: Engine): Promise<string[]> {
  const home = ((await $.env.get('USERPROFILE')) || (await $.env.get('HOME')) || '').replace(/\\/g, '/')
  if (!home) return []
  const root = `${home}/.claude/CLAUDE.md`
  const text = await $.fs.read(root).catch(() => undefined)
  if (text === undefined) return []
  const dir = root.slice(0, root.lastIndexOf('/'))
  const imports = [...text.matchAll(/^@(\S+)\s*$/gm)].map(([, p]) =>
    p.startsWith('~/') ? home + p.slice(1) : ABS.test(p) ? p : `${dir}/${p}`)
  return [root, ...imports]
}

// What the engine holds now. Taken on the first prompt with none stored: a session's start, and after a
// compaction, which clears it (compaction.ts; $ may not cross an import, and the engine takes one
// session.start and one session.compact hook per plugin, both in compaction.ts). A reload keeps it.
async function baseline($: Engine): Promise<void> {
  const now: Seen = {}
  for (const path of await watched($)) {
    try {
      const { mtimeMs } = await $.fs.stat(path)
      now[path] = { mtimeMs, text: await $.fs.read(path) }
    } catch {
      // A file that cannot be read now is picked up by the next baseline.
    }
  }
  await update($, seen, () => now)
}

// Each rule keyed by its section and bold lead-in (else its opening words), its text the value.
export function rules(text: string): Map<string, string> {
  const m = new Map<string, string>()
  let section = ''
  let key = ''
  for (const line of text.replace(/\r\n/g, '\n').split('\n')) {
    if (/^#{1,6} /.test(line)) { section = line.replace(/^#+\s*/, ''); key = ''; continue }
    if (!line.trim()) { key = ''; continue }
    if (key && /^\s/.test(line)) { m.set(key, `${m.get(key)}\n${line}`); continue }
    const lead = /\*\*(.+?)\*\*/.exec(line)?.[1] ?? line.replace(/^\s*[-*]\s+/, '').slice(0, 60)
    key = section ? `${section} › ${lead}` : lead
    for (let n = 2; m.has(key); n++) key = `${section} › ${lead} (${n})`
    m.set(key, line)
  }
  return m
}

export function note(path: string, before: string, after: string): string | undefined {
  const a = rules(before)
  const b = rules(after)
  const changed = [...b.keys()].filter(k => a.has(k) && a.get(k) !== b.get(k))
  const added = [...b.keys()].filter(k => !a.has(k))
  const removed = [...a.keys()].filter(k => !b.has(k))
  const names = [...changed.map(k => `changed: ${k}`), ...added.map(k => `added: ${k}`), ...removed.map(k => `removed: ${k}`)]
  if (!names.length) return undefined
  const list = names.slice(0, LIST_CAP).map(n => `- ${n}`).join('\n')
    + (names.length > LIST_CAP ? `\n- and ${names.length - LIST_CAP} more` : '')
  const quoted = [...changed, ...added].map(k => b.get(k)).join('\n\n')
  const head = `The global instructions in ${path} changed during this session, so what you loaded at its start is out of date:\n${list}\n`
  const tail = removed.length ? '\nA removed rule no longer applies.' : ''
  if (names.length <= LIST_CAP && quoted.length <= QUOTE_CAP) return `${head}\nThe new text, which replaces what you hold:\n\n${quoted}\n${tail}`
  return `${head}\nRead these rules from the file before your next step that they could touch; the new text replaces what you hold.${tail}`
}

async function changes($: Engine): Promise<string[]> {
  const before = await read($, seen)
  if (!Object.keys(before).length) { await baseline($); return [] }
  const after: Seen = { ...before }
  const notes: string[] = []
  for (const [path, old] of Object.entries(before)) {
    const stat = await $.fs.stat(path).catch(() => undefined)
    if (!stat || stat.mtimeMs === old.mtimeMs) continue
    const text = await $.fs.read(path)
    after[path] = { mtimeMs: stat.mtimeMs, text }
    const n = note(path, old.text, text)
    if (n) notes.push(n)
  }
  await update($, seen, () => after)
  return notes
}

export const register: Register = on => {
  on('prompt.submit', async ($, e, next) => {
    if (e.command) return next(e)
    let notes: string[] = []
    try {
      notes = await changes($)
    } catch {
      // A failed check must never hold a prompt back.
    }
    return next(notes.length ? { ...e, context: [...(e.context ?? []), ...notes] } : e)
  })
}
