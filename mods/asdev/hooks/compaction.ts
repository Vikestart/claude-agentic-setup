import { atom, read, update } from 'claude-code'
import type { EngineInterface as Engine, Register, ToolCallResult } from 'claude-code'
import { keepEndings, refusal } from './guards'
import { unpushed } from './shipped'

// Graceful compaction (implementation_plan step 3): the session compacts at a clean break it chooses,
// not mid-step at the 330k backstop. Replaces hooks/after_compact.py (archived). Subagents (step 4)
// get notes on their own context size instead; replaces hooks/context_guard.py (archived).

// Below this a compaction saves too little to be worth a break. The first note comes here (planned
// checkpoints now count), then a nudge every +50k (~200k, 250k…) for any clean break.
const TRIGGER_FROM = 150_000
const NUDGE_EVERY = 50_000
const TRIGGER_LINE = 'ready to compact'
// Final messages measured 2026-10-01: median ~700 characters, longest 3,260.
const REPLY_CAP = 6000
const DOCS = ['implementation_plan.md', 'task.md', 'handover.md', 'roadmap.md']

// Was the "When compacting" rule in CLAUDE.shared.md; given to every main-chat compaction without its own.
const INSTRUCTIONS = 'Keep: the current phase and task, decisions with their reasons, open questions, and any '
  + 'uncommitted, unpushed or undeployed state. Drop: tool output, file contents (they are on disk) '
  + 'and resolved dead ends.'

// The budgets live in the audit suite's doc_hygiene.py (one source), so the mod asks it.
const BUDGET_PY = 'import json, os, sys\n'
  + "sys.path.insert(0, os.path.expanduser('~/.claude/skills/asdev-web-audit/scripts'))\n"
  + 'from doc_hygiene import over_budget\n'
  + 'print(json.dumps(over_budget(sys.argv[1])))'

// A subagent that has only read by this point is exploring too widely; one past the limit re-reads
// all of it on every turn (measured 2026-09-30: the costliest threads ran at 500k–960k).
const AGENT_SCOUT = 125_000
const AGENT_LIMIT = 250_000
const WRITES = new Set(['Edit', 'Write', 'NotebookEdit'])
// Work done through the shell (a patch, a commit, a suite or gate run) is progress, not exploring.
const SHELL_WORK = /\b(patch\.py|quiet\.py|falsify\.py|audit_all\.py|git\s+(commit|apply|merge)|sed\s+-i|crlf\.py\s+--fix)\b/
// Agents that write nothing by design: the "nothing written yet" note would be wrong for them.
const READ_ONLY = /reviewer|^(Explore|Plan|claude-code-guide)$/

const AGENT_INSTRUCTIONS = 'This is a subagent. Keep verbatim: the brief you were given (the task, '
  + 'the files you own, the checks to run, what to report). Keep: the steps done and the files '
  + 'changed, findings with file paths and lines, and the exact next step. Drop: tool output and '
  + 'file contents (they are on disk).'

const nudgedAt = atom({ plugin: 'asdev', key: 'nudgedAt' } as const, 0)
const lastReply = atom({ plugin: 'asdev', key: 'lastReply' } as const, '')
// Read by band.tsx too: the app shows nothing while a compaction it did not start runs (traps.md, Mods).
const compactingSince = atom({ plugin: 'asdev', key: 'compactingSince' } as const, 0)
const STALE_COMPACTION = 10 * 60_000
const cacheAt = atom({ plugin: 'asdev', key: 'cacheAt' } as const, 0)

const k = (n: number) => `${Math.round(n / 1000)}k`

function armed(tokens: number): string {
  return `This session's context is at ${k(tokens)}, so a compaction is now worth a break. At the `
    + 'next compaction checkpoint the plan marks (⟲), or the end of a phase, update the working docs '
    + 'so they hold the current state, then end that reply with a line telling the owner a compaction '
    + `is starting and takes about a minute, and make the very last line exactly: ${TRIGGER_LINE}`
}

function nudge(tokens: number): string {
  return `This session's context is at ${k(tokens)}. At the next clean break (a commit, a phase `
    + 'boundary, a finished step; never mid-edit), update the working docs so they hold the current '
    + 'state, then end that reply with a line telling the owner a compaction is starting and takes '
    + `about a minute, and make the very last line exactly: ${TRIGGER_LINE}`
}

async function tick($: Engine, since: number) {
  while ((await read($, compactingSince)) === since) {
    const s = Math.round(((await $.clock.now()) - since) / 1000)
    $.ui.status(`Compacting… ${s} s`)
    $.ui.invalidate('ui.render')
    await $.clock.sleep(1000)
  }
  $.ui.status(undefined)
  $.ui.invalidate('ui.render')
}

async function budgetNote($: Engine, cwd: string): Promise<string> {
  try {
    const { exitCode, stdout } = await $.process.run(['python', '-c', BUDGET_PY, cwd], { timeoutMs: 10_000 })
    const found = exitCode === 0 ? (JSON.parse(stdout) as [string, string, string][]) : []
    if (!found.length) return ''
    return '\n\nOver their size budget, read again and again by you and every agent — trim them at the '
      + "next phase boundary (the phase-completion routine's trim step), not now mid-task:\n"
      + found.map(([rel, over, how]) => `- ${rel}: ${over} — ${how}`).join('\n')
  } catch {
    // Suite missing or broken: the docs notice still stands.
    return ''
  }
}

async function afterCompact($: Engine, cwd: string): Promise<string> {
  const present: string[] = []
  for (const name of DOCS) {
    if (await $.fs.exists(`${cwd}/.docs/${name}`)) present.push(`.docs/${name}`)
  }
  // Sessions started at the htdocs root work in a project one level down, whose docs are unknown here.
  let text = present.length
    ? `Context was just compacted. Before continuing, re-read ${present.join(', ')} — the files are `
      + 'the record; where they and the summary disagree, the files win.' + await budgetNote($, cwd)
    : 'Context was just compacted. Before continuing, re-read the .docs/ working files '
      + '(implementation_plan.md, task.md) of the project you are working in, if it has them — '
      + 'where they and the summary disagree, the files win.'
  // The summary paraphrases or drops the last reply, and it is usually what the owner is answering.
  const reply = await read($, lastReply)
  if (reply) {
    text += '\n\nYour last message to the owner before the compaction, verbatim — the owner may be '
      + `replying to it:\n<<<\n${reply}\n>>>`
  }
  return text
}

type Agent = { tokens: number; readOnly?: boolean; wrote: boolean; scouted: boolean; notedAt: number }
// Per loop, from each step's usage; a reload starts it over, which costs at most one repeated note.
const agents = new Map<string, Agent>()

async function agentNote($: Engine, id: string, tool: string, r: ToolCallResult, command = ''): Promise<ToolCallResult> {
  const a = agents.get(id)
  if (!a) return r
  if (WRITES.has(tool) || SHELL_WORK.test(command)) a.wrote = true
  let note = ''
  if (a.tokens >= (a.notedAt ? a.notedAt + NUDGE_EVERY : AGENT_LIMIT)) {
    a.notedAt = a.tokens
    note = `Your context is at ${k(a.tokens)}, and every further turn re-reads all of it. Finish the `
      + 'current step, then hand back: what is done, what is left, and the exact next step.'
  } else if (a.tokens >= AGENT_SCOUT && !a.wrote && !a.scouted) {
    a.scouted = true
    a.readOnly ??= READ_ONLY.test((await $.agent.list()).find(x => x.id === id)?.type ?? '')
    if (!a.readOnly) {
      note = `Your context is at ${k(a.tokens)} and you have not written anything yet. Stop exploring `
        + 'and hand back: what you found, with file paths, and a proposed split of the rest into '
        + 'smaller briefs.'
    }
  }
  return note ? { ...r, context: [...(r.context ?? []), note] } : r
}

function isTrigger(answer: string): boolean {
  const lines = answer.trim().split('\n')
  return lines[lines.length - 1].replace(/[`*_.!]/g, '').trim().toLowerCase() === TRIGGER_LINE
}

// Set when a stop held by another Stop hook (a /goal) was let through to compact; that hook's reason
// is the prompt that carries the work on once the compaction is done.
let resume = ''

async function remember($: Engine, answer: string) {
  const reply = answer.length > REPLY_CAP ? `${answer.slice(0, REPLY_CAP)}\n[… cut at ${REPLY_CAP} characters]` : answer
  await update($, lastReply, () => reply)
}

function carryOn($: Engine) {
  if (!resume) return
  const text = `The compaction is done; carry on. The goal's last check said:\n${resume}`
  resume = ''
  void $.prompt.submit({ text }).catch(() => undefined)
}

async function wantsCompact($: Engine, answer: string): Promise<boolean> {
  if (!isTrigger(answer)) return false
  const { context } = await $.session.usage()
  return (context.tokens ?? 0) >= TRIGGER_FROM
}

export const register: Register = on => {
  on('tool.call', async ($, e, next) => {
    // The guards run here: the engine takes one unmatched tool.call hook per plugin. The tool's
    // arguments sit on `e` itself, beside `tool` (there is no `e.input`; reading it let every call
    // through, live check 2026-10-02).
    // A relative path (`cat notes.md`) is the session's; `$.fs` needs it whole.
    const readFile = async (path: string) =>
      $.fs.read(/^([A-Za-z]:|[\\/])/.test(path) ? path : `${await $.session.cwd()}/${path}`)
    const why = await refusal(e.tool, e, readFile)
    if (why) return { deny: why }
    const kept = await keepEndings(e.tool, e, readFile)
    let r = await next((kept ?? e) as typeof e)
    if (r.deny !== undefined) return r
    // Said, so a Write meant to turn the file LF does not pass for done.
    if (kept) r = { ...r, context: [...(r.context ?? []), `Saved with CRLF endings to match the existing file. If LF was intended, run \`python ~/.claude/skills/asdev-web-audit/scripts/crlf.py --fix --lf ${String(e.file_path)}\`.`] }
    if (e.agentId) return agentNote($, e.agentId, e.tool, r, String((e as { command?: unknown }).command ?? ''))
    const { context } = await $.session.usage()
    const tokens = context.tokens
    if (tokens === undefined) return r
    const last = await read($, nudgedAt)
    if (tokens < (last ? last + NUDGE_EVERY : TRIGGER_FROM)) return r
    await update($, nudgedAt, () => tokens)
    return { ...r, context: [...(r.context ?? []), (last ? nudge : armed)(tokens)] }
  })

  on('turn.step', async function* ($, e, next) {
    const r = yield* next(e)
    // A main-thread reply refreshes its prompt cache; band.tsx counts down from here.
    if (!e.agentId && r.usage) {
      const t = await $.clock.now()
      await update($, cacheAt, () => t)
    }
    if (e.agentId && r.usage) {
      const u = r.usage
      const tokens = u.input_tokens + u.cache_read_input_tokens + u.cache_creation_input_tokens
      const a = agents.get(e.agentId)
      if (a) a.tokens = tokens
      else agents.set(e.agentId, { tokens, wrote: false, scouted: false, notedAt: 0 })
    }
    return r
  })

  on('turn.complete', async ($, e, next) => {
    const r = await next(e)
    if (e.agentId || e.isAborted || !e.answer.trim()) return r
    await remember($, e.answer)
    if (!(await wantsCompact($, e.answer))) return r
    // Not awaited: the command waits for this turn to end. `$.session.compact` is refused in the app.
    // Either way the goal is carried on: a compaction that never happened must not strand it, nor
    // leave its prompt for a later, unrelated compaction (a no-op once session.compact sent it).
    $.command.run({ command: 'compact', args: INSTRUCTIONS }).catch(() => undefined).then(() => carryOn($))
    return r
  })

  // Under /goal the goal's Stop hook blocks every stop, so the turn never ends and turn.complete never
  // comes; the compact command cannot run from here either (it would wait on the held turn). So the
  // stop is let through, turn.complete compacts, and the goal's reason is sent on afterwards.
  on('classic.Stop', async ($, e, next) => {
    const r = await next(e)
    // Sent back once only (`stop_hook_active`): the corrected reply may still name the push.
    if (!r.block && !e.stop_hook_active) {
      const why = await unpushed(e.last_assistant_message ?? '', e.cwd, argv => $.process.run(argv, { timeoutMs: 10_000 }))
      if (why) return { ...r, block: why }
    }
    if (!r.block || !(await wantsCompact($, e.last_assistant_message ?? ''))) return r
    resume = r.block
    return { ...r, block: undefined }
  })

  on('session.compact', async ($, e, next) => {
    if (e.agentId) {
      // Best effort: whether the engine compacts a subagent at all is unverified (probe c).
      const a = agents.get(e.agentId)
      if (a) a.notedAt = 0
      return next(e.instructions ? e : { ...e, instructions: AGENT_INSTRUCTIONS })
    }
    const since = await $.clock.now()
    await update($, compactingSince, () => since)
    $.ui.toast('Compacting the conversation — about a minute. A message sent now waits for it.', { timeoutMs: 15_000 })
    // The ticker ends when the flag clears; an unload mid-wait is not an error.
    void tick($, since).catch(() => undefined)
    try {
      return await next(e.instructions ? e : { ...e, instructions: INSTRUCTIONS })
    } finally {
      await update($, compactingSince, () => 0)
      await update($, nudgedAt, () => 0)
      carryOn($)
    }
  })

  // A reload during a compaction unloads the old ticker before it clears its status line, and
  // leaves "Compacting… N s" frozen under the prompt (seen 2026-10-04). A reload fires session.start
  // again: pick the count back up, or clear what was left. A flag older than any compaction is one
  // whose clean-up never ran.
  on('session.start', async ($, e, next) => {
    const r = await next(e)
    const since = await read($, compactingSince)
    if (since && (await $.clock.now()) - since < STALE_COMPACTION) {
      void tick($, since).catch(() => undefined)
    } else {
      if (since) await update($, compactingSince, () => 0)
      $.ui.status(undefined)
    }
    return r
  })

  on('classic.SessionStart', async ($, e, next) => {
    const r = await next(e)
    if (e.source !== 'compact') return r
    try {
      const text = await afterCompact($, e.cwd)
      return { ...r, additionalContext: [...(r.additionalContext ?? []), text] }
    } catch {
      // A broken notice must never break the session start.
      return r
    }
  })
}
