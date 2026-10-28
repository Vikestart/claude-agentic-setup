@@@ mods/asdev/hooks/guards.ts
name: a heredoc runs
expect: (fail) a shell heredoc is refused
<<<<<<< OLD
  if (ps ? hasHereString(cmd) : hasHeredoc(cmd)) {
======= NEW
  if (ps ? hasHereString(cmd) : false) {
>>>>>>> END

name: a quoted << counts as a heredoc
expect: (fail) a shell heredoc is refused
<<<<<<< OLD
  const plain = unquoted(cmd).replace(/\(\(
======= NEW
  const plain = cmd.replace(/\(\(
>>>>>>> END

name: a piped suite runner runs
expect: (fail) a suite runner piped into a filter is refused
<<<<<<< OLD
  if (pipesRunner(cmd, ps)) {
======= NEW
  if (false) {
>>>>>>> END

name: pipefail no longer lets the pipe through
expect: (fail) a suite runner piped into a filter is refused
<<<<<<< OLD
  if (/(^|[;&\s])(set\s+-[a-z]*o\s+pipefail|-o\s+pipefail)\b/.test(plain)) return false
======= NEW
>>>>>>> END

name: a whole read of a big file runs
expect: (fail) a whole read of a file over 1,000 lines is refused
<<<<<<< OLD
  return lines ? bigRefusal(path, lines) : undefined
======= NEW
  return undefined
>>>>>>> END

name: a big file counts as small
expect: (fail) cat of a whole file over 1,000 lines is refused
<<<<<<< OLD
  return lines > BIG_FILE ? lines : undefined
======= NEW
  return undefined
>>>>>>> END

name: cat of a big file runs
expect: (fail) cat of a whole file over 1,000 lines is refused
<<<<<<< OLD
  if (path && lines) return bigRefusal(path, lines)
======= NEW
>>>>>>> END

name: a foreground wait loop runs
expect: (fail) a foreground wait loop is refused
<<<<<<< OLD
  if (!input.run_in_background && waitLoop(cmd, ps)) {
======= NEW
  if (false) {
>>>>>>> END

name: a background wait loop is refused too
expect: (fail) a foreground wait loop is refused
<<<<<<< OLD
  if (!input.run_in_background && waitLoop(cmd, ps)) {
======= NEW
  if (waitLoop(cmd, ps)) {
>>>>>>> END

name: the runner before a semicolon counts for a later pipe
expect: (fail) a suite runner piped into a filter is refused
<<<<<<< OLD
    const before = cmd.slice(start + cut,
======= NEW
    const before = cmd.slice(start,
>>>>>>> END

name: a Write over a CRLF file comes out LF
expect: (fail) a Write over a CRLF file keeps CRLF
<<<<<<< OLD
  return { ...input, content: input.content.replace(/\r?\n/g, '\r\n') }
======= NEW
  return undefined
>>>>>>> END

name: an LF file is turned CRLF too
expect: (fail) a Write over a CRLF file keeps CRLF
<<<<<<< OLD
  if (!crlf || crlf * 2 < (old.match(/\n/g) ?? []).length) return undefined
======= NEW
>>>>>>> END

name: a line range of a big file is refused too
expect: (fail) a whole read of a file over 1,000 lines is refused
<<<<<<< OLD
  if (!path || input.offset !== undefined || input.limit !== undefined || NOT_TEXT.test(path)) return undefined
======= NEW
  if (!path || NOT_TEXT.test(path)) return undefined
>>>>>>> END

name: model passes on any Agent call
expect: (fail) an Agent call passing model is refused, whatever its type
<<<<<<< OLD
  if (input.model === undefined) return undefined
======= NEW
  return undefined
>>>>>>> END

name: model is refused only on a setup definition
expect: (fail) an Agent call passing model is refused, whatever its type
<<<<<<< OLD
  if (input.model === undefined) return undefined
======= NEW
  if (input.model === undefined || !/^(opus|fable|sonnet|haiku)-/.test(type)) return undefined
>>>>>>> END

name: any word naming a runner counts, not only the program run
expect: (fail) a suite runner piped into a filter is refused
<<<<<<< OLD
RUNNER.test(program(before))
======= NEW
before.split(/\s+/).some(w => RUNNER.test(w))
>>>>>>> END

name: the PowerShell tool is not checked
expect: (fail) the PowerShell tool gets the same rules
<<<<<<< OLD
  PowerShell: (input, readFile) => shell(input, readFile, true),
======= NEW
>>>>>>> END

name: a for-loop retry poll runs
expect: (fail) a foreground wait loop is refused
<<<<<<< OLD
    if (/\bsleep\b/.test(m[1]) && /\bbreak\b/.test(m[1])) return true
======= NEW
    if (false) return true
>>>>>>> END

name: a while-loop's sleep anywhere in the command counts
expect: (fail) a foreground wait loop is refused
<<<<<<< OLD
    if (/\bsleep\b/.test(m[2])) return true
  }
======= NEW
    if (/\bsleep\b/.test(m[2])) return true
  }
  if (/\b(until|while)\b[\s\S]*\bsleep\b/.test(plain)) return true
>>>>>>> END

name: a runner piped into tee runs
expect: (fail) a suite runner piped into a filter is refused
<<<<<<< OLD
|less|more|tee|Select-Object
======= NEW
|less|more|Select-Object
>>>>>>> END

name: any mention of pipefail lets the pipe through
expect: (fail) a suite runner piped into a filter is refused
<<<<<<< OLD
  if (/(^|[;&\s])(set\s+-[a-z]*o\s+pipefail|-o\s+pipefail)\b/.test(plain)) return false
======= NEW
  if (/\bpipefail\b/.test(cmd)) return false
>>>>>>> END

name: shell arithmetic counts as a heredoc
expect: (fail) a shell heredoc is refused
<<<<<<< OLD
  const plain = unquoted(cmd).replace(/\(\([^)]*\)\)/g, m => ' '.repeat(m.length))
======= NEW
  const plain = unquoted(cmd)
>>>>>>> END

name: Git Bash drive paths are not converted
expect: (fail) cat of a whole file over 1,000 lines is refused
<<<<<<< OLD
  return path.replace(/^\/([a-zA-Z])\//, (_, d: string) => `${d.toUpperCase()}:/`)
======= NEW
  return path
>>>>>>> END

name: shell scripts are rewritten to CRLF
expect: (fail) a Write over a CRLF file keeps CRLF
<<<<<<< OLD
 || LF_ONLY.test(String(input.file_path ?? ''))) return undefined
======= NEW
) return undefined
>>>>>>> END

name: verify.py piped into a filter runs
expect: (fail) a suite runner piped into a filter is refused
<<<<<<< OLD
|verify\.py|falsify
======= NEW
|falsify
>>>>>>> END

name: a PowerShell loop keyword anywhere counts, not only as a statement
expect: (fail) the PowerShell tool gets the same rules
<<<<<<< OLD
(?<=(?:^|[;\n{}(=])\s*(?::\w+\s+)?)(do|while|for|foreach)\b
======= NEW
\b(do|while|for|foreach)\b
>>>>>>> END

name: a PowerShell do-loop poll runs
expect: (fail) the PowerShell tool gets the same rules
<<<<<<< OLD
(?<=(?:^|[;\n{}(=])\s*(?::\w+\s+)?)(do|while|for|foreach)\b
======= NEW
(?<=(?:^|[;\n{}(=])\s*(?::\w+\s+)?)(while|for|foreach)\b
>>>>>>> END

name: a PowerShell for-loop retry poll runs
expect: (fail) the PowerShell tool gets the same rules
<<<<<<< OLD
(?<=(?:^|[;\n{}(=])\s*(?::\w+\s+)?)(do|while|for|foreach)\b
======= NEW
(?<=(?:^|[;\n{}(=])\s*(?::\w+\s+)?)(do|while)\b
>>>>>>> END

name: a sleep after a PowerShell loop counts as the loop's
expect: (fail) the PowerShell tool gets the same rules
<<<<<<< OLD
    if (/\b(Start-Sleep|sleep)\b/i.test(body[0])
======= NEW
    if (/\b(Start-Sleep|sleep)\b/i.test(plain.slice(at))
>>>>>>> END

name: a PowerShell for-loop needs no break to count
expect: (fail) the PowerShell tool gets the same rules
<<<<<<< OLD
(!kw.startsWith('for') || /\bbreak\b/i.test(body[0]))
======= NEW
true
>>>>>>> END

name: a here-string inside a quoted string counts
expect: (fail) the PowerShell tool gets the same rules
<<<<<<< OLD
    else if (c === '"' || c === "'") quote = c
======= NEW
>>>>>>> END

name: an @ mid-word opens a here-string
expect: (fail) the PowerShell tool gets the same rules
<<<<<<< OLD
(i === 0 || /[\s=(:,;]/.test(cmd[i - 1])) &&
======= NEW
>>>>>>> END

name: a PowerShell here-string runs
expect: (fail) the PowerShell tool gets the same rules
<<<<<<< OLD
  if (ps ? hasHereString(cmd) : hasHeredoc(cmd)) {
======= NEW
  if (ps ? false : hasHeredoc(cmd)) {
>>>>>>> END

name: a final newline counts as one more line
expect: (fail) a whole read of a file over 1,000 lines is refused
<<<<<<< OLD
 - (text.endsWith('\n') ? 1 : 0)
======= NEW
>>>>>>> END

name: |& is not taken as a pipe
expect: (fail) a suite runner piped into a filter is refused
<<<<<<< OLD
/(?<!\|)\|(?!\|)&?/g
======= NEW
/(?<!\|)\|(?!\|)/g
>>>>>>> END

name: collecting tests counts as a suite run
expect: (fail) a suite runner piped into a filter is refused
<<<<<<< OLD
--(collect-only|co|version|help)
======= NEW
--(version|help)
>>>>>>> END

name: python -m names no program
expect: (fail) a suite runner piped into a filter is refused
<<<<<<< OLD
        if (words[i] === '-m') { i++; break }
======= NEW
        if (words[i] === '-m') break
>>>>>>> END

name: an interpreter's script is not taken as the program
expect: (fail) a suite runner piped into a filter is refused
<<<<<<< OLD
    else if (PYTHON.test(base) || (/^\$[\w:{}]+$/.test(w) && !PS_OPERATOR.test(words[i + 1] ?? ''))) {
======= NEW
    else if (false) {
>>>>>>> END

name: a variable assignment hides the runner
expect: (fail) a suite runner piped into a filter is refused
<<<<<<< OLD
    if (/^\w+=/.test(w) || WRAPPER.test(base) || KEYWORD.test(w)) i++
======= NEW
    if (WRAPPER.test(base) || KEYWORD.test(w)) i++
>>>>>>> END

name: a wrapper hides the runner
expect: (fail) a suite runner piped into a filter is refused
<<<<<<< OLD
    if (/^\w+=/.test(w) || WRAPPER.test(base) || KEYWORD.test(w)) i++
======= NEW
    if (/^\w+=/.test(w) || KEYWORD.test(w)) i++
>>>>>>> END

name: timeout hides the runner
expect: (fail) a suite runner piped into a filter is refused
<<<<<<< OLD
    else if (w === 'timeout') {
======= NEW
    else if (false) {
>>>>>>> END

name: uv run hides the runner
expect: (fail) a suite runner piped into a filter is refused
<<<<<<< OLD
    } else if (RUN_VERB.test(w) && words[i + 1] === 'run') i += 2
======= NEW
    }
>>>>>>> END

name: a block's { does not start the command before a pipe
expect: (fail) a suite runner piped into a filter is refused
<<<<<<< OLD
|\n|\(|(?<!\$)\{|(?<![<>&])
======= NEW
|\n|\(|(?<![<>&])
>>>>>>> END

name: a variable's ${ starts a command too
expect: (fail) a suite runner piped into a filter is refused
<<<<<<< OLD
|\n|\(|(?<!\$)\{|(?<![<>&])
======= NEW
|\n|\(|\{|(?<![<>&])
>>>>>>> END

name: then, do and ! hide the runner
expect: (fail) a suite runner piped into a filter is refused
<<<<<<< OLD
WRAPPER.test(base) || KEYWORD.test(w)) i++
======= NEW
WRAPPER.test(base)) i++
>>>>>>> END

name: a path-qualified wrapper hides the runner
expect: (fail) a suite runner piped into a filter is refused
<<<<<<< OLD
WRAPPER.test(base) || KEYWORD.test(w)) i++
======= NEW
WRAPPER.test(w) || KEYWORD.test(w)) i++
>>>>>>> END

name: cmd /c hides the runner it runs
expect: (fail) the PowerShell tool gets the same rules
<<<<<<< OLD
    else if (/^cmd(\.exe)?$/i.test(base) && /^\/[ck]$/i.test(words[i + 1] ?? '')) return program(words.slice(i + 2).join(' '))
======= NEW
>>>>>>> END

name: a variable holding the interpreter hides the runner
expect: (fail) the PowerShell tool gets the same rules
<<<<<<< OLD
    else if (PYTHON.test(base) || (/^\$[\w:{}]+$/.test(w) && !PS_OPERATOR.test(words[i + 1] ?? ''))) {
======= NEW
    else if (PYTHON.test(base)) {
>>>>>>> END

name: an apostrophe in a comment hides a here-string
expect: (fail) the PowerShell tool gets the same rules
<<<<<<< OLD
    else if (c === '#' && (i === 0
======= NEW
    else if (false && (i === 0
>>>>>>> END

name: a here-string after : is no argument
expect: (fail) the PowerShell tool gets the same rules
<<<<<<< OLD
/[\s=(:,;]/.test(cmd[i - 1])
======= NEW
/[\s=(,;]/.test(cmd[i - 1])
>>>>>>> END

name: a here-string after , is no argument
expect: (fail) the PowerShell tool gets the same rules
<<<<<<< OLD
/[\s=(:,;]/.test(cmd[i - 1])
======= NEW
/[\s=(:;]/.test(cmd[i - 1])
>>>>>>> END

name: a here-string after ; is no argument
expect: (fail) the PowerShell tool gets the same rules
<<<<<<< OLD
/[\s=(:,;]/.test(cmd[i - 1])
======= NEW
/[\s=(:,]/.test(cmd[i - 1])
>>>>>>> END

name: a PowerShell loop assigned to a variable runs
expect: (fail) the PowerShell tool gets the same rules
<<<<<<< OLD
(?<=(?:^|[;\n{}(=])\s*(?::\w+\s+)?)(do|while|for|foreach)\b
======= NEW
(?<=(?:^|[;\n{}(])\s*(?::\w+\s+)?)(do|while|for|foreach)\b
>>>>>>> END

name: a variable compared with an operator runs a suite again
expect: (fail) the PowerShell tool gets the same rules
<<<<<<< OLD
    else if (PYTHON.test(base) || (/^\$[\w:{}]+$/.test(w) && !PS_OPERATOR.test(words[i + 1] ?? ''))) {
======= NEW
    else if (PYTHON.test(base) || /^\$[\w:{}]+$/.test(w)) {
>>>>>>> END

name: a comment right after a brace hides a here-string again
expect: (fail) the PowerShell tool gets the same rules
<<<<<<< OLD
    else if (c === '#' && (i === 0 || /[\s;{}()]/.test(cmd[i - 1]))) {
======= NEW
    else if (c === '#' && (i === 0 || /[\s;]/.test(cmd[i - 1]))) {
>>>>>>> END

@@@ mods/asdev/hooks/compaction.ts
name: relative paths are not resolved against the session
expect: (fail) cat of a whole file over 1,000 lines is refused
<<<<<<< OLD
? path : `${await $.session.cwd()}/${path}`)
======= NEW
? path : path)
>>>>>>> END

name: the kept line endings never reach the tool
expect: (fail) a Write over a CRLF file keeps CRLF
<<<<<<< OLD
    let r = await next((kept ?? e) as typeof e)
======= NEW
    let r = await next(e)
>>>>>>> END

name: the shipped-state check is not consulted
expect: (fail) a reply claiming a push while commits are unpushed
<<<<<<< OLD
      if (why) return { ...r, block: why }
======= NEW
>>>>>>> END

name: a claimed push is sent back again and again
expect: (fail) a reply claiming a push while commits are unpushed
<<<<<<< OLD
    if (!r.block && !e.stop_hook_active) {
======= NEW
    if (!r.block) {
>>>>>>> END

@@@ mods/asdev/hooks/shipped.ts
name: a negated claim counts as a claim
expect: (fail) a reply claiming a push while commits are unpushed
<<<<<<< OLD
    if (!NEGATED.test(before)) return true
======= NEW
    return true
>>>>>>> END

name: an up-to-date branch is sent back too
expect: (fail) a reply claiming a push while commits are unpushed
<<<<<<< OLD
  const m = /^## (\S+?)\.\.\.(\S+) \[ahead (\d+)/.exec(head)
======= NEW
  const m = /^## (\S+?)\.\.\.(\S+)() ?/.exec(head)
>>>>>>> END

@@@ mods/asdev/hooks/band.tsx
name: the band hides before the first context figure
expect: (fail) terminal: the band stays up before the first context figure
<<<<<<< OLD
    const tokens = context?.tokens
======= NEW
    const tokens = context?.tokens
    if (tokens === undefined) return next(e)
>>>>>>> END

@@@ mods/asdev/hooks/compaction.ts
name: the guards are not consulted
expect: (fail) a shell heredoc is refused
<<<<<<< OLD
    if (why) return { deny: why }
======= NEW
>>>>>>> END

name: the guards read e.input, which live calls lack
expect: (fail) a shell heredoc is refused
<<<<<<< OLD
    const why = await refusal(e.tool, e, readFile)
======= NEW
    const why = await refusal(e.tool, (e as { input?: unknown }).input, readFile)
>>>>>>> END

name: no checkpoint note at 150k
expect: (fail) checkpoints armed at 150k
<<<<<<< OLD
(last ? nudge : armed)(tokens)
======= NEW
nudge(tokens)
>>>>>>> END

name: the trigger line compacts below 150k
expect: (fail) the trigger line compacts with the instructions, from 150k only
<<<<<<< OLD
  if (tokens < TRIGGER_FROM) return false
  if (!asksOwner(answer)) return true
======= NEW
  if (!asksOwner(answer)) return true
>>>>>>> END

name: under /goal the trigger stop stays blocked
expect: (fail) under /goal: the trigger stop is let through
<<<<<<< OLD
    return { ...r, block: undefined }
======= NEW
    return r
>>>>>>> END

name: the split note ignores writes
expect: (fail) no split note for an agent that wrote
<<<<<<< OLD
  } else if (a.tokens >= AGENT_SCOUT && !a.wrote && !a.scouted) {
======= NEW
  } else if (a.tokens >= AGENT_SCOUT && !a.scouted) {
>>>>>>> END

name: read-only agents get the split note
expect: (fail) no split note for an agent that wrote
<<<<<<< OLD
    if (!a.readOnly) {
======= NEW
    if (true) {
>>>>>>> END

name: the hand-back note comes only once
expect: (fail) a subagent: a split note at 125k
<<<<<<< OLD
a.notedAt ? a.notedAt + NUDGE_EVERY : AGENT_LIMIT
======= NEW
a.notedAt ? Infinity : AGENT_LIMIT
>>>>>>> END

name: subagent compactions get no instructions
expect: (fail) instructions added only when none are given
<<<<<<< OLD
      return next(e.instructions ? e : { ...e, instructions: AGENT_INSTRUCTIONS })
======= NEW
      return next(e)
>>>>>>> END

name: the CRLF rewrite goes unsaid
expect: (fail) a Write over a CRLF file keeps CRLF
<<<<<<< OLD
    if (kept) r =
======= NEW
    if (false) r =
>>>>>>> END

name: a gate run through the shell is not work
expect: (fail) no split note for an agent that wrote
<<<<<<< OLD
  if (WRITES.has(tool) || SHELL_WORK.test(command)) a.wrote = true
======= NEW
  if (WRITES.has(tool)) a.wrote = true
>>>>>>> END

