import { atom, read, update } from 'claude-code'
import type { EngineInterface as Engine, Register, ToolCallResult } from 'claude-code'
import { keepEndings, refusal } from './guards'
import { limitNotes } from './limits'
import { unpushed } from './shipped'

// Graceful compaction (implementation_plan step 3): the session compacts at a clean break it chooses,
// not mid-step at the 330k backstop. Replaces hooks/after_compact.py (archived). Subagents (step 4)
// get notes on their own context size instead; replaces hooks/context_guard.py (archived).

// A compaction saves too little to be worth a break until the context has grown this much past where
// the session started (its first reply after a start, /clear or compaction): with a fixed 150k, a chat
// that starts big with knowledge or tools compacted early, and again soon after (owner, 2026-10-30).
// The first note comes there (planned checkpoints now count), then a nudge every +50k for any clean break.
const FIRST_GAP = 100_000
// A start never measured (a chat open across this change, a fork): the fixed 150k it had before.
const START_UNKNOWN = 50_000
const NUDGE_EVERY = 50_000
const TRIGGER_LINE = 'ready to compact'
// Up to here, finishing the step in hand is a fine reason to wait for the break; past it the automatic
// compaction (~300k of the 330k window) is close enough to cut in mid-step (work setup, back-ported 2026-10-28).
const CAREFUL_FROM = 230_000
// Past this a main chat may not go on with its working docs older than CAREFUL_FROM: the automatic
// compaction would lose what only the chat holds. Until a .docs file is written, only the docs,
// searches and git's read commands run.
const DOCS_BY = 280_000
const DOCS_PATH = /(^|[\\/])\.docs[\\/]/
const GIT_READ = /^\s*git\s+(status|log|diff|show)\b/
// Also the tools that only ask, stop or wait: none of them grows the context much.
const SEARCH = new Set(['Glob', 'Grep', 'TodoWrite', 'AskUserQuestion', 'TaskStop', 'Monitor', 'ToolSearch'])
// Final messages measured 2026-10-01: median ~700 characters, longest 3,260.
const REPLY_CAP = 6000
const DOCS = ['implementation_plan.md', 'task.md', 'handover.md', 'roadmap.md']
// A compaction started at the end of a reply that asks the owner something cuts in before they can
// answer (seen 2026-10-24, a Tilspire chat asking for canvas picks). Said in the notes, and enforced.
const NOT_WITH_A_QUESTION = 'Never in a reply that asks the owner a question or waits on their pick: '
  + 'ask first, and compact at the break after they answer.'

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
// The main chat's prompt cache lasts an hour from the last reply (the 1-hour TTL; a session in usage
// overage drops to 5 minutes, which the engine does not report). Past it, the next message writes the
// whole context to the cache again at the full write price.
export const CACHE_TTL = 3600_000
// The session state does not outlive the app, but the server's cache does: each chat's last reply is
// also kept in the store under its session id, so the band's timer survives a restart (owner, 2026-10-30).
export const CACHE_STORE = 'cacheAts'
export const asTimes = (v: unknown): Record<string, number> =>
  v && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, number> : {}
// The context size at the last write to a .docs file in this main chat; a compaction clears it.
const docsAt = atom({ plugin: 'asdev', key: 'docsAt' } as const, 0)
// rules.ts's record of the instructions as loaded; declared again here because the engine reads only
// atoms declared in the file that uses them.
const rulesSeen = atom({ plugin: 'asdev', key: 'rules' } as const, {} as Record<string, { mtimeMs: number; text: string }>)
const limitNoted = atom({ plugin: 'asdev', key: 'limitNoted' } as const, {} as Record<string, { line: number; resetsAt?: string }>)
// The context the main chat started from, 0 until measured. Kept in the store under the session id
// too, since the session state does not outlive the app; the oldest of BASE_KEEP chats drop out.
const contextBase = atom({ plugin: 'asdev', key: 'contextBase' } as const, 0)
// Set at a start, /clear or compaction: the next main-thread reply is measured. 'if-new' for a startup
// the store does not know, measured only when the chat has no earlier replies.
const measureBase = atom({ plugin: 'asdev', key: 'measureBase' } as const, '' as '' | 'now' | 'if-new')
const BASE_STORE = 'contextBases'
const BASE_KEEP = 50

async function storedBase($: Engine, id: string): Promise<number> {
  const v = id ? asTimes(await $.store.get(BASE_STORE).catch(() => undefined))[id] : undefined
  return typeof v === 'number' && v > 0 ? v : 0
}

// Where the first compaction note comes. Never later than CAREFUL_FROM: past it the automatic
// compaction is close, so a chat that starts very big still gets its clean break.
export async function compactFrom($: Engine): Promise<number> {
  const base = (await read($, contextBase)) || await storedBase($, await $.session.id().catch(() => ''))
  return Math.min((base || START_UNKNOWN) + FIRST_GAP, CAREFUL_FROM)
}

// A chat the app reopens with no start kept (open across this change, or out of the last BASE_KEEP)
// arrives as a startup too; its size now is not its start, and would push its first note to 230k
// (review, 2026-10-30). The reply being measured may already be in the transcript.
async function isNewChat($: Engine): Promise<boolean> {
  const messages = await $.session.messages().catch(() => [])
  return Array.isArray(messages) && messages.filter(m => m.role === 'assistant').length <= 1
}

const k = (n: number) => `${Math.round(n / 1000)}k`

function armed(tokens: number): string {
  return `This session's context is at ${k(tokens)}, so a compaction is now worth a break. At the `
    + 'next compaction checkpoint the plan marks (⟲), or the end of a phase, update the working docs '
    + 'so they hold the current state, then end that reply with a line telling the owner a compaction '
    + `is starting and takes about a minute, and make the very last line exactly: ${TRIGGER_LINE}. `
    + NOT_WITH_A_QUESTION
}

function nudge(tokens: number): string {
  const then = 'update the working docs so they hold the current state, then end that reply with a '
    + 'line telling the owner a compaction is starting and takes about a minute, and make the very '
    + `last line exactly: ${TRIGGER_LINE}. ${NOT_WITH_A_QUESTION}`
  if (tokens < CAREFUL_FROM) {
    return `This session's context is at ${k(tokens)}. At the next clean break (a commit, a phase `
      + 'boundary, a finished step; never mid-edit), and finishing what you are doing first is fine up '
      + `to about ${k(CAREFUL_FROM)}, ${then}`
  }
  return `This session's context is at ${k(tokens)}, past ${k(CAREFUL_FROM)}: the automatic compaction `
    + 'is close and cuts in mid-step. Start nothing new and avoid large reads; finish only the step in '
    + `hand, then at that next clean break ${then} Never pass ${k(DOCS_BY)} with the docs not updated: `
    + 'past it, every other tool is refused until a .docs file is written.'
}

type Call = { tool: string; file_path?: unknown; notebook_path?: unknown; command?: unknown }

// The refusal past DOCS_BY, or nothing. A project without working docs is never held.
async function docsHold($: Engine, e: Call): Promise<string | undefined> {
  const tokens = (await $.session.usage()).context.tokens ?? 0
  if (tokens < DOCS_BY || (await read($, docsAt)) >= CAREFUL_FROM) return undefined
  const path = String(e.file_path ?? e.notebook_path ?? '')
  if ((WRITES.has(e.tool) || e.tool === 'Read') && DOCS_PATH.test(path)) return undefined
  if (SEARCH.has(e.tool) || ((e.tool === 'Bash' || e.tool === 'PowerShell') && GIT_READ.test(String(e.command ?? '')))) return undefined
  try {
    const cwd = await $.session.cwd()
    let any = false
    for (const name of DOCS) any ||= await $.fs.exists(`${cwd}/.docs/${name}`)
    if (!any) return undefined
  } catch {
    // No session folder or file access: nothing to hold the session to.
    return undefined
  }
  return `Refused: this session is at ${k(tokens)}, past ${k(DOCS_BY)}, and its .docs have not been updated `
    + `since ${k(CAREFUL_FROM)}. Update the working docs in .docs/ now - they are what survives the `
    + 'compaction - then end that reply with a line telling the owner a compaction is starting, and make '
    + `the very last line exactly: ${TRIGGER_LINE}. ${NOT_WITH_A_QUESTION}`
}

async function tick($: Engine, since: number) {
  while ((await read($, compactingSince)) === since) {
    const now = await $.clock.now()
    // A hot reload mid-compaction drops the wait that clears the flag, and nothing else clears it before
    // the next prompt: the count ran on long after the compaction (work setup, seen 2026-10-27).
    if (now - since >= STALE_COMPACTION) {
      await update($, compactingSince, s => (s === since ? 0 : s))
      break
    }
    const s = Math.round((now - since) / 1000)
    $.ui.status(`Compacting… ${s} s`)
    $.ui.invalidate('ui.render')
    await $.clock.sleep(1000)
  }
  $.ui.status(undefined)
  $.ui.invalidate('ui.render')
}

// The toast and the ticker, once per compaction: false when one is already under way or queued, so a
// second trigger while our /compact waits queues no second one (work setup, seen 2026-10-27: it
// compacted the fresh summary again).
async function showCompacting($: Engine): Promise<boolean> {
  const now = await $.clock.now()
  let started = false
  await update($, compactingSince, s => (s && now - s < STALE_COMPACTION ? s : ((started = true), now)))
  if (!started) return false
  $.ui.toast('Compacting the conversation — about a minute. A message sent now waits for it.', { timeoutMs: 15_000 })
  // The ticker ends when the flag clears; an unload mid-wait is not an error.
  void tick($, now).catch(() => undefined)
  return true
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

// `seen`: a fingerprint of each file the agent read whole. Rereading an unchanged file adds it to the
// context a second time (2026-10-25: a Tilspire builder read two 35k-character docs twice each, about
// 35k tokens, and stopped at 250k).
type Agent = { tokens: number; readOnly?: boolean; wrote: boolean; scouted: boolean; notedAt: number; seen?: Map<string, string> }
// Per loop, from each step's usage; a reload starts it over, which costs at most one repeated note.
const agents = new Map<string, Agent>()

async function agentNote($: Engine, id: string, tool: string, r: ToolCallResult, command = ''): Promise<ToolCallResult> {
  const a = agents.get(id)
  if (!a) return r
  if (WRITES.has(tool) || SHELL_WORK.test(command)) a.wrote = true
  let note = ''
  if (a.tokens >= (a.notedAt ? a.notedAt + NUDGE_EVERY : AGENT_LIMIT)) {
    a.notedAt = a.tokens
    a.readOnly ??= READ_ONLY.test((await $.agent.list()).find(x => x.id === id)?.type ?? '')
    // A builder that hands back with nothing committed leaves its successor to piece the work together.
    note = `Your context is at ${k(a.tokens)}, and every further turn re-reads all of it. Finish the `
      + (a.readOnly ? 'current step, then hand back: '
        : 'current step, commit what you have as a `wip` commit on your branch (never push), then hand back: ')
      + 'what is done, what is left, and the exact next step.'
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

// FNV-1a over the text, with its length: enough to tell an unchanged file without keeping it.
function fingerprint(text: string): string {
  let h = 0x811c9dc5
  for (let i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 0x01000193)
  return `${text.length}:${(h >>> 0).toString(16)}`
}

const wholeRead = (e: { tool: string; offset?: unknown; limit?: unknown; pages?: unknown; file_path?: unknown }) =>
  e.tool === 'Read' && e.offset === undefined && e.limit === undefined && e.pages === undefined && typeof e.file_path === 'string'

function isTrigger(answer: string): boolean {
  const lines = answer.trim().split('\n')
  return lines[lines.length - 1].replace(/[`*_.!]/g, '').trim().toLowerCase() === TRIGGER_LINE
}

// A line that ends in a question mark (once trailing markdown or an aside in brackets is stripped), or
// asks Y/N; code never asks, fenced or inline, so a paste-ready note asks nothing. A missed question is
// the costlier error, so a heading ending in ? holds the compaction too (work setup, 2026-10-27).
function asksOwner(text: string): boolean {
  let fenced = false
  for (const line of text.split('\n')) {
    if (/^\s*(```|~~~)/.test(line)) { fenced = !fenced; continue }
    if (fenced) continue
    const plain = line.replace(/`[^`]*`/g, '')
    if (/[[(]\s*Y\s*\/\s*N\s*[\])]|\bY\/N[\s*_.]*$/i.test(plain)) return true
    if (/[?？](\s*\([^)]*\))?[\s*_)"'‘’“”]*$/.test(plain)) return true
  }
  return false
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
  const tokens = context.tokens ?? 0
  if (tokens < await compactFrom($)) return false
  if (!asksOwner(answer)) return true
  // Held for the answer: the next tool call repeats the nudge, so the compaction is not lost.
  await update($, nudgedAt, () => tokens - NUDGE_EVERY)
  return false
}

export const register: Register = on => {
  on('tool.call', async ($, e, next) => {
    // The guards run here: the engine takes one unmatched tool.call hook per plugin. The tool's
    // arguments sit on `e` itself, beside `tool` (there is no `e.input`; reading it let every call
    // through, live check 2026-10-02).
    // A relative path (`cat notes.md`) is the session's; `$.fs` needs it whole.
    const readFile = async (path: string) =>
      $.fs.read(/^([A-Za-z]:|[\\/])/.test(path) ? path : `${await $.session.cwd()}/${path}`)
    const why = (await refusal(e.tool, e, readFile)) ?? (e.agentId ? undefined : await docsHold($, e as Call))
    if (why) return { deny: why }
    const kept = await keepEndings(e.tool, e, readFile)
    const agent = e.agentId ? agents.get(e.agentId) : undefined
    let print = ''
    if (agent && wholeRead(e)) {
      const path = String(e.file_path)
      try {
        print = fingerprint(await readFile(path))
      } catch {
        // Unreadable here (missing, binary): the Read tool reports that itself.
      }
      if (print && agent.seen?.get(path) === print) {
        return { deny: `You already read all of ${path} earlier in this task and it has not changed since, `
          + 'so it is still in your context: use that copy. To look at part of it again, read only those '
          + 'lines (offset and limit).' }
      }
    }
    let r = await next((kept ?? e) as typeof e)
    if (agent && print && r.deny === undefined) (agent.seen ??= new Map()).set(String(e.file_path), print)
    if (r.deny !== undefined) return r
    if (!e.agentId && WRITES.has(e.tool) && DOCS_PATH.test(String((e as Call).file_path ?? (e as Call).notebook_path ?? ''))) {
      const at = (await $.session.usage()).context.tokens ?? 0
      await update($, docsAt, () => at)
    }
    // Said, so a Write meant to turn the file LF does not pass for done.
    const limits = e.agentId ? [] : await limitNotes($).catch(() => [] as string[])
    if (limits.length) r = { ...r, context: [...(r.context ?? []), ...limits] }
    if (kept) r = { ...r, context: [...(r.context ?? []), `Saved with CRLF endings to match the existing file. If LF was intended, run \`python ~/.claude/skills/asdev-web-audit/scripts/crlf.py --fix --lf ${String(e.file_path)}\`.`] }
    if (e.agentId) return agentNote($, e.agentId, e.tool, r, String((e as { command?: unknown }).command ?? ''))
    const { context } = await $.session.usage()
    const tokens = context.tokens
    if (tokens === undefined) return r
    const last = await read($, nudgedAt)
    if (tokens < (last ? last + NUDGE_EVERY : await compactFrom($))) return r
    await update($, nudgedAt, () => tokens)
    return { ...r, context: [...(r.context ?? []), (last ? nudge : armed)(tokens)] }
  })

  on('turn.step', async function* ($, e, next) {
    const r = yield* next(e)
    // A main-thread reply refreshes its prompt cache; band.tsx counts down from here.
    if (!e.agentId && r.usage) {
      const t = await $.clock.now()
      await update($, cacheAt, () => t)
      const id = await $.session.id().catch(() => '')
      if (id) {
        // Only the entries still inside the hour, so the map never grows past the chats in use.
        const kept = Object.entries(asTimes(await $.store.get(CACHE_STORE))).filter(([, at]) => t - at < CACHE_TTL)
        await $.store.set(CACHE_STORE, { ...Object.fromEntries(kept), [id]: t })
      }
      const how = await read($, measureBase)
      if (how) await update($, measureBase, () => '')
      if (how === 'now' || (how === 'if-new' && await isNewChat($))) {
        const u = r.usage
        const tokens = u.input_tokens + u.cache_read_input_tokens + u.cache_creation_input_tokens
        await update($, contextBase, () => tokens)
        if (id) {
          const kept = Object.entries(asTimes(await $.store.get(BASE_STORE))).filter(([key]) => key !== id).slice(1 - BASE_KEEP)
          await $.store.set(BASE_STORE, { ...Object.fromEntries(kept), [id]: tokens })
        }
      }
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
    // One already under way or queued is enough: its own end carries the goal on. The flag clears when
    // the command resolves, even if session.compact never ran.
    void showCompacting($)
      .then(started => started && $.command.run({ command: 'compact', args: INSTRUCTIONS })
        .catch(() => undefined)
        .then(() => update($, compactingSince, () => 0))
        .then(() => carryOn($)))
      .catch(() => undefined)
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
      // After a compaction the agent no longer holds what it read.
      const a = agents.get(e.agentId)
      if (a) { a.notedAt = 0; a.seen = undefined }
      return next(e.instructions ? e : { ...e, instructions: AGENT_INSTRUCTIONS })
    }
    await showCompacting($)
    try {
      return await next(e.instructions ? e : { ...e, instructions: INSTRUCTIONS })
    } finally {
      await update($, compactingSince, () => 0)
      await update($, nudgedAt, () => 0)
      await update($, docsAt, () => 0)
      // The compacted session reloads the instructions: rules.ts takes a new baseline on the next prompt.
      await update($, rulesSeen, () => ({}))
      // The summary may drop a usage note, so the next prompt or tool call repeats it.
      await update($, limitNoted, () => ({}))
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
    // Measured again only once a compaction is done: one cancelled or failed leaves the context as it
    // was, and measuring that would put the first note off to 230k (review, 2026-10-30). A start the
    // store already holds is the app reopening the chat: its start stands. A resume keeps its stored
    // start; a fork keeps its parent's.
    const how = e.source === 'compact' || e.source === 'clear' ? 'now'
      : e.source === 'startup' && !(await storedBase($, await $.session.id().catch(() => ''))) ? 'if-new' : ''
    if (how) await update($, measureBase, () => how)
    // /clear and a resume in the same process go on under another session id with the last chat's
    // state: its start, and the nudge and docs marks that would put off the next note or lift the hold.
    if (how || e.source === 'resume') await update($, contextBase, () => 0)
    if (e.source === 'clear' || e.source === 'resume') {
      await update($, nudgedAt, () => 0)
      await update($, docsAt, () => 0)
    }
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
