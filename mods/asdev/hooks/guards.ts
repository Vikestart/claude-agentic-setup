// Enforced rules (implementation_plan step 5): each guard refuses what a CLAUDE.shared.md rule
// forbids and says what to do instead, so the rule no longer needs to be read to be kept.
// Main chat and subagents alike. A guard that throws is skipped by the engine (fails open).

const AUDIT = '~/.claude/skills/asdev-web-audit/scripts'
// Measured 2026-10-01: whole reads of 1,000+ line files were among the largest repeated contexts.
const BIG_FILE = 1000
const LF_ONLY = /\.(sh|bash|zsh|sql)$/i
const NOT_TEXT = /\.(png|jpe?g|gif|webp|bmp|ico|pdf|ipynb)$/i
// Definitions that set their own model; the setup's agent files (agents/opus-*, fable-*, sonnet-*).
const DEFINITION = /^(opus|fable|sonnet)-/
const RUNNER = /\b(pytest|phpunit|unittest|audit_all\.py|self_test\.py|verify\.py|falsify\.py|test_\w+\.py|\w+_test\.py|npm (run )?test|bun test|node --test|claude plugin test)\b/
// `tee` too: `runner | tee log` reports tee's exit code. PowerShell's own filters for its tool.
const FILTER = /^\s*(head|tail|grep|egrep|rg|sort|uniq|wc|cut|awk|sed|less|more|tee|Select-Object|select|Select-String|sls|Sort-Object|Measure-Object|Out-String|findstr)\b/i
// A command that only reads, names or describes a runner: `grep x test_setup.py | head`,
// `pip show pytest | head`, `phpunit --version | head`, `falsify.py --help | grep` run no suite.
const READER = /^\s*(head|tail|grep|egrep|rg|sort|uniq|wc|cut|awk|sed|less|more|cat|type|ls|find|git|echo|diff|Get-Content|gc|Select-String)\b|^\s*(pip3?|composer|npm)\s+(show|info|list|view)\b|--(version|help)\b/i
// Inline code (`python -c "…"`, `node -e '…'`) only names what it imports.
const INLINE_CODE = /\s-[ce]\s+("[^"]*"|'[^']*')/g

// The command's text outside quotes, with each quoted stretch blanked to spaces: a `<<` or `|` in a
// quoted argument (a grep pattern, a message) is not the shell's. PowerShell escapes with a
// backtick, so a backslash there is a path character.
function unquoted(cmd: string, ps = false): string {
  let out = ''
  let quote = ''
  const esc = ps ? '`' : '\\'
  for (let i = 0; i < cmd.length; i++) {
    const c = cmd[i]
    if (quote) {
      if (c === esc && quote === '"') { out += '  '; i++; continue }
      if (c === quote) quote = ''
      out += ' '
    } else if (c === esc) {
      out += '  '
      i++
    } else if (c === '"' || c === "'") {
      quote = c
      out += ' '
    } else out += c
  }
  return out
}

// `<<EOF`, `<<-EOF`, `<< 'EOF'`, `<<"EOF"`; not `<<<` (a one-line here-string) nor `$((1 << 3))`.
// The delimiter's quotes are blanked by `unquoted`, so a word or a quote may follow.
export function hasHeredoc(cmd: string): boolean {
  // Arithmetic `$((1 << n))` / `(( x << 2 ))` shifts, not a heredoc.
  const plain = unquoted(cmd).replace(/\(\([^)]*\)\)/g, m => ' '.repeat(m.length))
  for (const m of plain.matchAll(/(?<!<)<<(?!<)-?/g)) {
    const at = (m.index ?? 0) + m[0].length
    const rest = cmd.slice(at).replace(/^\s*/, '')
    if (/^['"]?[A-Za-z_]/.test(rest)) return true
  }
  return false
}

// A suite runner piped into a filter loses the runner's exit code (the pipe reports the filter's),
// so a red run reads green.
export function pipesRunner(cmd: string, ps = false): boolean {
  const plain = unquoted(cmd, ps)
  // Set as a shell option, not merely mentioned (`echo pipefail; …`).
  if (/(^|[;&\s])(set\s+-[a-z]*o\s+pipefail|-o\s+pipefail)\b/.test(plain)) return false
  const parts = plain.split(/(?<!\|)\|(?!\|)/)
  for (let i = 0; i < parts.length - 1; i++) {
    // Only the command right before the pipe: in `runner; ls | head` the pipe is not the runner's.
    const cut = Math.max(...[...parts[i].matchAll(/;|&&|\|\||\n|\(/g)].map(m => (m.index ?? 0) + m[0].length), 0)
    const at = offset(parts, i)
    // The raw text, so a quoted path still names its runner (`python "$HOME/…/verify.py"`).
    const before = cmd.slice(at + cut, at + parts[i].length).replace(INLINE_CODE, ' ')
    if (RUNNER.test(before) && !READER.test(before) && FILTER.test(parts[i + 1])) return true
  }
  return false
}

function offset(parts: string[], i: number): number {
  return parts.slice(0, i).reduce((n, p) => n + p.length + 1, 0)
}

type Input = Record<string, unknown>
// The caller's `$.fs.read`: the engine does not let `$` cross an import.
type ReadFile = (path: string) => Promise<string>
// Each returns the refusal, or nothing when the call may run.
type Check = (input: Input, readFile: ReadFile) => string | undefined | Promise<string | undefined>

// A wait loop in the foreground: the turn sits idle, the owner cannot interject, and repeated polls
// each re-read the whole context (1,432 such waits mined 2026-10-02).
// Bash: a `while`/`until` whose `do … done` body sleeps (not `while read`, a batch over input), or a
// `for` whose body sleeps and breaks (a retry poll). PowerShell: the same over `{ … }` bodies.
// Separate commands that merely name the words (`grep -c until f; grep -c sleep f`) are not loops.
export function waitLoop(cmd: string, ps = false): boolean {
  const plain = unquoted(cmd, ps)
  if (ps) {
    const sleeps = /\{[^{}]*\b(Start-Sleep|sleep)\b[^{}]*\}/i
    return (/\b(while|until|do)\b/i.test(plain) && sleeps.test(plain))
      || (/\b(for|foreach)\b/i.test(plain) && sleeps.test(plain) && /\bbreak\b/i.test(plain))
  }
  const body = String.raw`\bdo\b((?:(?!\bdone\b)[\s\S])*)\bdone\b`
  for (const m of plain.matchAll(new RegExp(String.raw`\b(while|until)\b(?![^;\n]*\bread\b)[^;\n]*[;\n]\s*` + body, 'g'))) {
    if (/\bsleep\b/.test(m[2])) return true
  }
  for (const m of plain.matchAll(new RegExp(String.raw`\bfor\b[^;\n]*[;\n]\s*` + body, 'g'))) {
    if (/\bsleep\b/.test(m[1]) && /\bbreak\b/.test(m[1])) return true
  }
  return false
}

// `cat <one file>` and nothing else (a `-n`, a stderr redirect allowed): the shell's whole-file
// read, which the Read guard would refuse. PowerShell's `Get-Content` and its aliases too.
const CAT = /^\s*(?:cat|type|gc|Get-Content)\s+(?:-(?:n|A|Raw|Path|LiteralPath)\s+)*(?:"([^"]+)"|'([^']+)'|([^\s|;&<>]+))\s*(?:2>(?:&1|\/dev\/null|\$null))?\s*$/i

// Git Bash's `/c/Users/…` is `C:/Users/…` to the file API.
function nativePath(path: string): string {
  return path.replace(/^\/([a-zA-Z])\//, (_, d: string) => `${d.toUpperCase()}:/`)
}

async function tooBig(path: string, readFile: ReadFile): Promise<number | undefined> {
  let lines = 0
  try {
    lines = (await readFile(path)).split('\n').length
  } catch {
    // Missing or unreadable: the tool itself says why.
    return undefined
  }
  return lines > BIG_FILE ? lines : undefined
}

function bigRefusal(path: string, lines: number): string {
  return `Refused: ${path} has ${lines} lines, and a whole read is re-read on every later turn. `
    + `Find what you need with \`python ${AUDIT}/code_map.py <file>\` and show it with `
    + `\`${AUDIT}/code_show.py\`, or Read a line range (offset and limit).`
}

// The Bash and PowerShell tools: the same rules, each in its shell's syntax.
async function shell(input: Input, readFile: ReadFile, ps: boolean) {
  const cmd = String(input.command ?? '')
  if (!input.run_in_background && waitLoop(cmd, ps)) {
    return 'Refused: a wait loop in the foreground. Start the long command with `run_in_background` '
      + 'and end the turn; its completion event wakes you. To watch for a condition, use the Monitor '
      + 'tool with the until-loop.'
  }
  const cat = CAT.exec(cmd)
  const path = cat && nativePath(cat[1] ?? cat[2] ?? cat[3])
  const lines = path ? await tooBig(path, readFile) : undefined
  if (path && lines) return bigRefusal(path, lines)
  if (ps ? /@['"][ \t]*\r?\n/.test(cmd) : hasHeredoc(cmd)) {
    return `Refused: a shell ${ps ? 'here-string' : 'heredoc'}. Multi-line content goes through the Write tool (to a file `
      + 'in the scratchpad when it is temporary), then run or pass the file: a commit message via '
      + `\`git commit -F <file>\`, several exact replacements via \`${AUDIT}/patch.py\`.`
  }
  if (pipesRunner(cmd, ps)) {
    return 'Refused: a suite runner piped into a filter reports the filter\'s exit code, so a red '
      + `run reads green. Run it through \`python ${AUDIT}/quiet.py -- <cmd>\`, which keeps the exit `
      + `code, logs the output and prints the summary${ps ? '' : '; or start the command with `set -o pipefail;`'}.`
  }
  return undefined
}

async function read(input: Input, readFile: ReadFile) {
  const path = String(input.file_path ?? '')
  if (!path || input.offset !== undefined || input.limit !== undefined || NOT_TEXT.test(path)) return undefined
  const lines = await tooBig(path, readFile)
  return lines ? bigRefusal(path, lines) : undefined
}

// The Write tool saves what it is given, so a rewrite of a CRLF file came out LF (probed 2026-10-02;
// Edit keeps them). `crlf.py` ran after edits 1,132 times. Returns the input to write instead.
export async function keepEndings(tool: string, input: Input, readFile: ReadFile): Promise<Input | undefined> {
  // Shell scripts and checksummed SQL must stay LF; a Write there may be the fix.
  if (tool !== 'Write' || typeof input.content !== 'string' || LF_ONLY.test(String(input.file_path ?? ''))) return undefined
  let old = ''
  try {
    old = await readFile(String(input.file_path ?? ''))
  } catch {
    // A new file: nothing to keep.
    return undefined
  }
  const crlf = (old.match(/\r\n/g) ?? []).length
  if (!crlf || crlf * 2 < (old.match(/\n/g) ?? []).length) return undefined
  return { ...input, content: input.content.replace(/\r?\n/g, '\r\n') }
}

function agent(input: Input) {
  const type = String(input.subagent_type ?? '')
  if (input.model === undefined || !DEFINITION.test(type)) return undefined
  return `Refused: ${type} sets its own model and effort; a \`model\` here would override them. `
    + 'Spawn it without `model`, or pick the definition with the model you want.'
}

const CHECKS: Record<string, Check> = {
  Bash: (input, readFile) => shell(input, readFile, false),
  PowerShell: (input, readFile) => shell(input, readFile, true),
  Read: read,
  Agent: agent,
}

// Called from compaction.ts's tool.call hook: the engine takes one unmatched tool.call hook per
// plugin, and hooks with a `{ tool }` matcher passed every test but never fired in the app (live
// check, 2026-10-02).
export async function refusal(tool: string, input: unknown, readFile: ReadFile): Promise<string | undefined> {
  return CHECKS[tool]?.((input ?? {}) as Input, readFile)
}
