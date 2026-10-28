// Enforced rules: each guard refuses what a CLAUDE.shared.md rule
// forbids and says what to do instead, so the rule no longer needs to be read to be kept.
// Main chat and subagents alike. A guard that throws is skipped by the engine (fails open).

const AUDIT = '~/.claude/skills/asdev-web-audit/scripts'
// Measured 2026-10-01: whole reads of 1,000+ line files were among the largest repeated contexts.
const BIG_FILE = 1000
const LF_ONLY = /\.(sh|bash|zsh|sql)$/i
const NOT_TEXT = /\.(png|jpe?g|gif|webp|bmp|ico|pdf|ipynb)$/i
// Matched against the program actually run and its arguments (see `program`), never a word in the
// arguments: `pip install pytest`, `code_map.py tests/test_crlf.py` run no suite.
const RUNNER = /^(?:\S*[\\/])?(pytest|py\.test|phpunit|unittest|audit_all\.py|self_test\.py|verify\.py|falsify\.py|test_\w+\.py|\w+_test\.py)(\.exe|\.bat)?(\s|$)|^(npm|yarn|pnpm)(\.cmd)?\s+(run\s+)?test\b|^bun\s+test\b|^node(\.exe)?\s+--test\b|^claude\s+plugin\s+test\b/i
// Collecting, or naming the version or usage, runs no suite.
const NOT_A_RUN = /(^|\s)--(collect-only|co|version|help)\b/
// `tee` too: `runner | tee log` reports tee's exit code. PowerShell's own filters for its tool.
const FILTER = /^\s*(head|tail|grep|egrep|rg|sort|uniq|wc|cut|awk|sed|less|more|tee|Select-Object|select|Select-String|sls|Sort-Object|Measure-Object|Out-String|findstr)\b/i
// Run their next word: `timeout 300 pytest`, `uv run pytest`, `& pytest` (PowerShell's call operator).
const WRAPPER = /^(env|time|nohup|exec|command|sudo|npx|bunx|&)$/
// Shell grammar before a command: `if …; then cmd`, `for …; do cmd`, `! cmd`.
const KEYWORD = /^(if|then|elif|else|do|while|until|!)$/
const RUN_VERB = /^(uv|poetry|pipenv|pdm|hatch)$/
const PYTHON = /^(python[\d.]*|py)(\.exe)?$/i
// A variable followed by an operator is a value being compared or split, not an interpreter run:
// `$deps -match "pytest" | Select-Object` filters a list.
const PS_OPERATOR = /^-[ci]?(eq|ne|gt|ge|lt|le|like|notlike|match|notmatch|contains|notcontains|in|notin|replace|split|join|is|isnot|as|and|or|xor|f)$/i

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

// PowerShell's `@"`/`@'` ending its line opens a here-string only where an argument starts (after
// whitespace, `=`, `(`, `:`, `,`, `;` or at the start) and outside a quoted string: `"user@"` at a
// line end is none. A `#` comment runs to its line end, so its apostrophe (`# don't`) opens no quote.
export function hasHereString(cmd: string): boolean {
  let quote = ''
  for (let i = 0; i < cmd.length; i++) {
    const c = cmd[i]
    if (quote) {
      if (c === '`' && quote === '"') i++
      else if (c === quote) quote = ''
    } else if (c === '`') i++
    else if (c === '#' && (i === 0 || /[\s;{}()]/.test(cmd[i - 1]))) {
      while (i + 1 < cmd.length && cmd[i + 1] !== '\n') i++
    } else if (c === '@' && (i === 0 || /[\s=(:,;]/.test(cmd[i - 1])) && /^['"][ \t]*\r?\n/.test(cmd.slice(i + 1))) return true
    else if (c === '"' || c === "'") quote = c
  }
  return false
}

// A suite runner piped into a filter loses the runner's exit code (the pipe reports the filter's),
// so a red run reads green.
export function pipesRunner(cmd: string, ps = false): boolean {
  const plain = unquoted(cmd, ps)
  // Set as a shell option, not merely mentioned (`echo pipefail; …`).
  if (/(^|[;&\s])(set\s+-[a-z]*o\s+pipefail|-o\s+pipefail)\b/.test(plain)) return false
  // `|&` pipes stderr too (bash); `||` is no pipe.
  const pipe = ps ? /(?<!\|)\|(?!\|)/g : /(?<!\|)\|(?!\|)&?/g
  let start = 0
  for (const p of plain.matchAll(pipe)) {
    const at = p.index ?? 0
    // Only the command right before the pipe: in `runner; ls | head` the pipe is not the runner's. A
    // block's `{` starts one too (`if ($?) { runner | …`); a variable's `${` does not.
    const cut = Math.max(...[...plain.slice(start, at).matchAll(/;|&&|\|\||\n|\(|(?<!\$)\{|(?<![<>&])&(?![&>])/g)].map(m => (m.index ?? 0) + m[0].length), 0)
    // The raw text, so a quoted path still names its runner (`python "$HOME/…/verify.py"`).
    const before = cmd.slice(start + cut, at)
    start = at + p[0].length
    const after = plain.slice(start).split(/(?<!\|)\|(?!\|)/)[0]
    if (FILTER.test(after) && RUNNER.test(program(before)) && !NOT_A_RUN.test(before)) return true
  }
  return false
}

// The program a command runs, with its arguments: past variable assignments and wrappers, and an
// interpreter's script or module (`python -m pytest`, `python "$HOME/…/verify.py"`) taken as the
// program; inline code (`python -c "import pytest…"`) is no program name. A variable as the program
// (`& $py -m pytest`) is read as an interpreter, and `cmd /c "…"` as the command it runs. Quotes are
// dropped from each word.
function program(cmd: string): string {
  const words = (cmd.match(/(?:"[^"]*"|'[^']*'|[^\s"'])+/g) ?? []).map(w => w.replace(/["']/g, ''))
  let i = 0
  while (i < words.length) {
    const w = words[i]
    const base = w.replace(/^.*[\\/]/, '')
    if (/^\w+=/.test(w) || WRAPPER.test(base) || KEYWORD.test(w)) i++
    else if (/^cmd(\.exe)?$/i.test(base) && /^\/[ck]$/i.test(words[i + 1] ?? '')) return program(words.slice(i + 2).join(' '))
    else if (w === 'timeout') {
      for (i++; words[i]?.startsWith('-'); i++);
      i++
    } else if (RUN_VERB.test(w) && words[i + 1] === 'run') i += 2
    else if (PYTHON.test(base) || (/^\$[\w:{}]+$/.test(w) && !PS_OPERATOR.test(words[i + 1] ?? ''))) {
      // Options up to the script; `-m` names the module run, `-W`/`-X` take a value.
      for (i++; words[i]?.startsWith('-'); i++) {
        if (words[i] === '-m') { i++; break }
        if (/^-[WX]$/.test(words[i])) i++
      }
      break
    } else break
  }
  return words.slice(i).join(' ')
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
  if (ps) return psWaitLoop(plain)
  const body = String.raw`\bdo\b((?:(?!\bdone\b)[\s\S])*)\bdone\b`
  for (const m of plain.matchAll(new RegExp(String.raw`\b(while|until)\b(?![^;\n]*\bread\b)[^;\n]*[;\n]\s*` + body, 'g'))) {
    if (/\bsleep\b/.test(m[2])) return true
  }
  for (const m of plain.matchAll(new RegExp(String.raw`\bfor\b[^;\n]*[;\n]\s*` + body, 'g'))) {
    if (/\bsleep\b/.test(m[1]) && /\bbreak\b/.test(m[1])) return true
  }
  return false
}

// The text inside the balanced `open … close` group that starts at `at` (after whitespace), and the
// index past it; undefined when none starts there or it never closes.
function group(s: string, at: number, open: string, close: string): [string, number] | undefined {
  while (/\s/.test(s[at] ?? '')) at++
  if (s[at] !== open) return undefined
  for (let i = at, depth = 0; i < s.length; i++) {
    if (s[i] === open) depth++
    else if (s[i] === close && --depth === 0) return [s.slice(at + 1, i), i + 1]
  }
  return undefined
}

// Only a loop statement counts, and only its own body: a `do` inside a path (`C:/x/do.txt`), or a
// sleep in a later script block (`foreach (…) { … break }; Start-Job { Start-Sleep 1 }`), is none.
function psWaitLoop(plain: string): boolean {
  for (const m of plain.matchAll(/(?<=(?:^|[;\n{}(=])\s*(?::\w+\s+)?)(do|while|for|foreach)\b/gi)) {
    const kw = m[1].toLowerCase()
    let at = (m.index ?? 0) + m[0].length
    if (kw !== 'do') {
      const cond = group(plain, at, '(', ')')
      if (!cond) continue
      at = cond[1]
    }
    const body = group(plain, at, '{', '}')
    if (!body || (kw === 'do' && !/^\s*(while|until)\b/i.test(plain.slice(body[1])))) continue
    if (/\b(Start-Sleep|sleep)\b/i.test(body[0]) && (!kw.startsWith('for') || /\bbreak\b/i.test(body[0]))) return true
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
    const text = await readFile(path)
    // A final newline ends the last line; it does not start another.
    lines = text.split('\n').length - (text.endsWith('\n') ? 1 : 0)
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
  if (ps ? hasHereString(cmd) : hasHeredoc(cmd)) {
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
  if (input.model === undefined) return undefined
  // Every Agent call, not only the setup's tiers: a `model` on general-purpose picks a model with no
  // effort to match, which the tier table exists to prevent.
  return `Refused: \`model\` on an Agent call overrides the definition's model and effort (here ${type || 'the default agent'}). `
    + 'Spawn it without `model`: pick the tier definition (agents/opus-*, sonnet-*, haiku-*, fable-*) with the model you want.'
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
