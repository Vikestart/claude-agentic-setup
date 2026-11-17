import { atom, read, update } from 'claude-code'
import type { EngineInterface as Engine } from 'claude-code'

// Each project's memory lives in its committed .docs/brain/ (the asdev-brain skill; owner,
// 2026-11-17). At every start the audit suite's brain.py points the harness's memory there and moves
// in what the old hidden folder holds, on every device, so no project is set up by hand.
const START_PY = 'import os, sys\n'
  + "sys.path.insert(0, os.path.expanduser('~/.claude/skills/asdev-web-audit/scripts'))\n"
  + 'import brain\n'
  + "sys.exit(brain.main(['start', '--json', '--project', sys.argv[1]]))"

type Step = { ok: boolean; warn?: boolean; step: string; message: string }
type Started = { skipped?: string; brain?: string; steps?: Step[]; newly_set?: boolean; moved?: number; index?: string }

// The harness reads the setting once, at the start, so in the session that set it memory still goes
// to the old folder. Kept for the session: a compaction or /clear repeats the line the summary may drop.
const brainSetUp = atom({ plugin: 'asdev', key: 'brainSetUp' } as const, '')
// A refusal is told once per device and project, not at every start: what to do about it is the
// owner's call. A store, since it must outlive the session.
const REFUSED = 'brainRefused'
// A freshly migrated index is not yet sorted and may run long; the rest stays in the file.
const INDEX_LINES = 80

const keepWriting = (brain: string) => 'This session the harness still saves memory in the old hidden '
  + `folder, so write new notes to \`.docs/brain/\` (${brain}) this session yourself, following the `
  + '`asdev-brain` skill.'

const asTold = (v: unknown): Record<string, string> =>
  v && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, string> : {}

function capped(index: string): string {
  const lines = index.replace(/\s+$/, '').split(/\r?\n/)
  return lines.length <= INDEX_LINES ? lines.join('\n')
    : [...lines.slice(0, INDEX_LINES), `… ${lines.length - INDEX_LINES} more line(s) in the file`].join('\n')
}

// What this start tells the session; '' when there is nothing to say.
export async function brainStart($: Engine, cwd: string, source: string): Promise<string> {
  const { stdout } = await $.process.run(['python', '-c', START_PY, cwd], { timeoutMs: 15_000 })
  let s: Started
  try {
    s = JSON.parse(stdout)
  } catch {
    return ''
  }
  // No git repo, no .docs/ (the htdocs root, a scratch folder): the harness default stands.
  if (!s || typeof s !== 'object' || Array.isArray(s) || s.skipped || !s.brain) return ''
  const brain = s.brain
  const parts: string[] = []
  if (s.newly_set) {
    await update($, brainSetUp, () => brain)
    parts.push(`This project's memory now lives in its committed second brain, set up just now on this device. ${keepWriting(brain)}`)
  }
  if (s.moved) parts.push(`${s.moved} note(s) from the old hidden memory folder were moved into the brain: `
    + 'commit `.docs/brain/` with the next commit.')
  for (const w of (s.steps ?? []).filter(x => x.ok && x.warn)) parts.push(`${w.step}: ${w.message}`)
  const failed = (s.steps ?? []).filter(x => !x.ok).map(x => `${x.step}: ${x.message}`).join('; ')
  const told = asTold(await $.store.get(REFUSED))
  if (failed && told[brain] !== failed) {
    parts.push(`The start-up hook could not finish this project's second brain (${brain}): ${failed}. `
      + 'Tell the owner what it means; the `asdev-brain` skill says how to finish it by hand.')
    await $.store.set(REFUSED, { ...told, [brain]: failed })
  } else if (!failed && brain in told) {
    // Fixed: a later refusal is news again.
    const { [brain]: _, ...rest } = told
    await $.store.set(REFUSED, rest)
  }
  // brain.py sends the index only when this start set up or moved something, so it is told once.
  if (s.index) parts.push(`The brain's index, \`.docs/brain/MEMORY.md\`:\n${capped(s.index)}`)
  if (!parts.length && source === 'clear') return brainReminder($)
  return parts.join('\n\n')
}

// For a compaction or /clear in the session that set the brain up; '' in any other.
export async function brainReminder($: Engine): Promise<string> {
  const brain = await read($, brainSetUp)
  return brain ? keepWriting(brain) : ''
}
