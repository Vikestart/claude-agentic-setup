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
(await refusal(e.tool, e, readFile))
======= NEW
(await refusal(e.tool, (e as { input?: unknown }).input, readFile))
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
  if (tokens < await compactFrom($)) return false
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


@@@ mods/asdev/hooks/compaction.ts
name: past 230k the nudge no longer asks for care
expect: (fail) checkpoints armed at 150k
<<<<<<< OLD
  if (tokens < CAREFUL_FROM) {
======= NEW
  if (true) {
>>>>>>> END

name: the nudge before 230k no longer allows finishing the step in hand
expect: (fail) checkpoints armed at 150k
<<<<<<< OLD
      + 'boundary, a finished step; never mid-edit), and finishing what you are doing first is fine up '
======= NEW
      + 'boundary, a finished step; never mid-edit), '
>>>>>>> END

name: past 280k nothing is held any more
expect: (fail) past 280k with the docs not updated since 230k
<<<<<<< OLD
    const why = (await refusal(e.tool, e, readFile)) ?? (e.agentId ? undefined : await docsHold($, e as Call))
======= NEW
    const why = await refusal(e.tool, e, readFile)
>>>>>>> END

name: a subagent is held too
expect: (fail) past 280k with the docs not updated since 230k
<<<<<<< OLD
(e.agentId ? undefined : await docsHold($, e as Call))
======= NEW
(await docsHold($, e as Call))
>>>>>>> END

name: a docs write no longer lifts the hold
expect: (fail) past 280k with the docs not updated since 230k
<<<<<<< OLD
      await update($, docsAt, () => at)
======= NEW
      void at
>>>>>>> END

name: a docs write before 230k counts as up to date
expect: (fail) past 280k with the docs not updated since 230k
<<<<<<< OLD
  if (tokens < DOCS_BY || (await read($, docsAt)) >= CAREFUL_FROM) return undefined
======= NEW
  if (tokens < DOCS_BY || (await read($, docsAt)) > 0) return undefined
>>>>>>> END

name: a compaction no longer resets the docs mark
expect: (fail) past 280k with the docs not updated since 230k
<<<<<<< OLD
      await update($, nudgedAt, () => 0)
      await update($, docsAt, () => 0)
      // The compacted session reloads
======= NEW
      await update($, nudgedAt, () => 0)
      // The compacted session reloads
>>>>>>> END

name: a project without .docs is held too
expect: (fail) past 280k a project without .docs is not held
<<<<<<< OLD
    if (!any) return undefined
======= NEW
>>>>>>> END

name: reading a .docs file is held
expect: (fail) past 280k with the docs not updated since 230k
<<<<<<< OLD
  if ((WRITES.has(e.tool) || e.tool === 'Read') && DOCS_PATH.test(path)) return undefined
======= NEW
  if (WRITES.has(e.tool) && DOCS_PATH.test(path)) return undefined
>>>>>>> END

name: git reads are held
expect: (fail) past 280k with the docs not updated since 230k
<<<<<<< OLD
const GIT_READ = /^\s*git\s+(status|log|diff|show)\b/
======= NEW
const GIT_READ = /^$/
>>>>>>> END

name: AskUserQuestion is held past 280k
expect: (fail) past 280k with the docs not updated since 230k
<<<<<<< OLD
'TodoWrite', 'AskUserQuestion', 'TaskStop',
======= NEW
'TodoWrite', 'TaskStop',
>>>>>>> END

name: TaskStop is held past 280k
expect: (fail) past 280k with the docs not updated since 230k
<<<<<<< OLD
'AskUserQuestion', 'TaskStop', 'Monitor',
======= NEW
'AskUserQuestion', 'Monitor',
>>>>>>> END

name: Monitor is held past 280k
expect: (fail) past 280k with the docs not updated since 230k
<<<<<<< OLD
'TaskStop', 'Monitor', 'ToolSearch'
======= NEW
'TaskStop', 'ToolSearch'
>>>>>>> END

name: ToolSearch is held past 280k
expect: (fail) past 280k with the docs not updated since 230k
<<<<<<< OLD
'Monitor', 'ToolSearch'])
======= NEW
'Monitor'])
>>>>>>> END

@@@ mods/asdev/hooks/rules.ts
name: a changed rule never rides a prompt
expect: (fail) an edit to an imported file reaches the next prompt once
<<<<<<< OLD
    return next(notes.length ? { ...e, context: [...(e.context ?? []), ...notes] } : e)
======= NEW
    return next(e)
>>>>>>> END

name: the stored copy is never updated, so a note repeats
expect: (fail) an edit to an imported file reaches the next prompt once
<<<<<<< OLD
  await update($, seen, () => after)
======= NEW
>>>>>>> END

name: a changed rule is not told apart from an unchanged one
expect: (fail) the note names changed, added and removed rules
<<<<<<< OLD
  const changed = [...b.keys()].filter(k => a.has(k) && a.get(k) !== b.get(k))
======= NEW
  const changed = [...b.keys()].filter(k => a.has(k))
>>>>>>> END

name: past the cap the whole text is quoted anyway
expect: (fail) past the cap the note lists names and asks for a read
<<<<<<< OLD
  if (names.length <= LIST_CAP && quoted.length <= QUOTE_CAP) return
======= NEW
  if (true) return
>>>>>>> END

@@@ mods/asdev/hooks/compaction.ts
name: a compaction keeps the old rules, so an earlier edit is told after it
expect: (fail) a compaction reloads the rules
<<<<<<< OLD
      await update($, rulesSeen, () => ({}))
======= NEW
>>>>>>> END

@@@ mods/asdev/hooks/compaction.ts
name: [Y/N] asks nothing
expect: (fail) what counts as asking
<<<<<<< OLD
    if (/[[(]\s*Y\s*\/\s*N\s*[\])]|\bY\/N[\s*_.]*$/i.test(plain)) return true
======= NEW
>>>>>>> END

@@@ mods/asdev/hooks/band.tsx
name: the account figure is read on every measure
expect: (fail) the account figure is read into the store
<<<<<<< OLD
(num(tried) && Math.abs(now - tried) < every)
======= NEW
false
>>>>>>> END

name: a try stamped ahead of now stops the reads
expect: (fail) the account figure is read into the store
<<<<<<< OLD
Math.abs(now - tried) < every
======= NEW
now - tried < every
>>>>>>> END

name: the try is never stamped
expect: (fail) the account figure is read into the store
<<<<<<< OLD
      await $.store.set('monthTry', now)
======= NEW
>>>>>>> END

name: a stuck read blocks every later one
expect: (fail) a stuck read stops blocking the next
<<<<<<< OLD
(fetching && Math.abs(now - fetching) < USAGE_BUSY)
======= NEW
fetching
>>>>>>> END

name: the figure is taken as dollars, not cents
expect: (fail) the account figure is read into the store
<<<<<<< OLD
used: x.used_credits / 100
======= NEW
used: x.used_credits
>>>>>>> END

name: an API key is sent to the usage read
expect: (fail) a failed read stores no figure
<<<<<<< OLD
    if (auth?.kind !== 'bearer') {
======= NEW
    if (!auth) {
>>>>>>> END

name: a session without the login wipes the figure
expect: (fail) a failed read stores no figure
<<<<<<< OLD
      await $.store.set('monthStatus', auth ? 'api-key' : 'no credential')
      return
======= NEW
      status = auth ? 'api-key' : 'no credential'
>>>>>>> END

name: a session without the login uses up the slot
expect: (fail) a failed read stores no figure
<<<<<<< OLD
    const auth = await $.session.authorize()
======= NEW
    await $.store.set('monthTry', now)
    const auth = await $.session.authorize()
>>>>>>> END

name: a disabled figure is stored
expect: (fail) a failed read stores no figure
<<<<<<< OLD
      if (x && x.is_enabled === true) {
======= NEW
      if (x) {
>>>>>>> END

name: a null figure reads as 0
expect: (fail) a failed read stores no figure
<<<<<<< OLD
num(x.used_credits) && num(x.monthly_limit)
======= NEW
true
>>>>>>> END

name: a failed read keeps the last figure
expect: (fail) a failed read stores no figure
<<<<<<< OLD
  await $.store.set('month', month)
======= NEW
  if (month) await $.store.set('month', month)
>>>>>>> END

name: a hung read never times out
expect: (fail) a hung read times out
<<<<<<< OLD
        $.clock.sleep(USAGE_WAIT).then(() => undefined),
======= NEW
>>>>>>> END

name: a new day keeps yesterday's start
expect: (fail) the account figure is read into the store
<<<<<<< OLD
    if (!day || day.day !== dayOf(now) || month.used < day.used) {
======= NEW
    if (!day || month.used < day.used) {
>>>>>>> END

name: a fall keeps the day's start
expect: (fail) the account figure is read into the store
<<<<<<< OLD
    if (!day || day.day !== dayOf(now) || month.used < day.used) {
======= NEW
    if (!day || day.day !== dayOf(now)) {
>>>>>>> END

name: the allowance keeps no buffer
expect: (fail) terminal: the account figure is a Today and a Month row
<<<<<<< OLD
const DAY_SHARE = 0.95
======= NEW
const DAY_SHARE = 1
>>>>>>> END

name: weekends count as working days
expect: (fail) terminal: the account figure is a Today and a Month row
<<<<<<< OLD
    n += w > 0 && w < 6 ? 1 : 0
======= NEW
    n += 1
>>>>>>> END

name: today is not counted among the working days left
expect: (fail) terminal: the account figure is a Today and a Month row
<<<<<<< OLD
  const days = workDays(y, mo, d.getDate())
======= NEW
  const days = workDays(y, mo, d.getDate() + 1)
>>>>>>> END

name: a month-end weekend divides by this month's working days
expect: (fail) terminal: a weekend that ends the month shows the next month's share
<<<<<<< OLD
m.limit / workDays(y, mo + 1, 1)
======= NEW
m.limit / workDays(y, mo, 1)
>>>>>>> END

name: the allowance reads what is left now, not this morning
expect: (fail) terminal: Today turns red past its allowance
<<<<<<< OLD
Math.max(0, m.limit - start) / days
======= NEW
Math.max(0, m.limit - m.used) / days
>>>>>>> END

name: Today never turns red
expect: (fail) terminal: Today turns red past its allowance
<<<<<<< OLD
  const over = spent > may
======= NEW
  const over = false
>>>>>>> END

name: yesterday's start counts as today's
expect: (fail) terminal: no figure yet today counts nothing spent today
<<<<<<< OLD
  const start = d?.day === dayOf(now) ? d.used : m.used
======= NEW
  const start = d?.used ?? m.used
>>>>>>> END

name: a figure from an earlier month shows
expect: (fail) terminal: a figure from an earlier month shows no row
<<<<<<< OLD
  if (!m || !sameMonth(m.at, now)) {
======= NEW
  if (!m) {
>>>>>>> END

name: a figure of the wrong shape shows
expect: (fail) terminal: a figure of the wrong shape shows no row
<<<<<<< OLD
num(m.used) && num(m.limit) && num(m.at)
======= NEW
num(m.limit) && num(m.at)
>>>>>>> END

name: the monthly window shows beside the account figure
expect: (fail) terminal: the account figure is a Today and a Month row
<<<<<<< OLD
|| tokens !== undefined, now)
      .filter(r => !months.length || !isMonthly(r.kind))
======= NEW
|| tokens !== undefined, now)
>>>>>>> END

name: the collapsed band keeps the monthly window
expect: (fail) terminal: the collapsed band shows Today and Month
<<<<<<< OLD
context.tokens !== undefined, now)
      .filter(r => !months.length || !isMonthly(r.kind))
======= NEW
context.tokens !== undefined, now)
>>>>>>> END

name: the collapsed band leaves the spend out
expect: (fail) terminal: the collapsed band shows Today and Month
<<<<<<< OLD
r.percentUsed / 100 })), ...months]
======= NEW
r.percentUsed / 100 }))]
>>>>>>> END

name: the collapsed band puts the spend before a usage window
expect: (fail) terminal: the collapsed band puts a usage window before the spend
<<<<<<< OLD
    const rows = [...pickLimits(
======= NEW
    const rows = [...months, ...pickLimits(
>>>>>>> END

name: the Month figure leaves out the pace
expect: (fail) desktop: the account figure is a Today and a Month row
<<<<<<< OLD
    value: `${Math.round(m.used / m.limit * 100)}% / ${Math.round(pace * 100)}%`,
======= NEW
    value: `${Math.round(m.used / m.limit * 100)}%`,
>>>>>>> END

name: the Today figure leaves out the pace
expect: (fail) desktop: the account figure is a Today and a Month row
<<<<<<< OLD
    value: `${Math.round(share * 100)}% / ${Math.round(dayPace * 100)}%`,
======= NEW
    value: `${Math.round(share * 100)}%`,
>>>>>>> END

name: Today's pace runs on past the working day
expect: (fail) desktop: Today's pace at 18:00 is 100%, the working hours only
<<<<<<< OLD
  const dayPace = Math.min(1, Math.max(0, (hour - WORK_FROM) / (WORK_TO - WORK_FROM)))
======= NEW
  const dayPace = Math.max(0, (hour - WORK_FROM) / (WORK_TO - WORK_FROM))
>>>>>>> END

@@@ mods/asdev/hooks/compaction.ts
name: inline code asks
expect: (fail) what counts as asking
<<<<<<< OLD
    const plain = line.replace(/`[^`]*`/g, '')
======= NEW
    const plain = line
>>>>>>> END

name: a second trigger queues a second /compact
expect: (fail) a trigger while its own /compact waits queues no second one
<<<<<<< OLD
  await update($, compactingSince, s => (s && now - s < STALE_COMPACTION ? s : ((started = true), now)))
======= NEW
  await update($, compactingSince, () => ((started = true), now))
>>>>>>> END

name: a compaction never seen to end counts on forever
expect: (fail) a compaction never seen to end stops counting after 10 minutes
<<<<<<< OLD
    if (now - since >= STALE_COMPACTION) {
======= NEW
    if (false) {
>>>>>>> END

@@@ mods/asdev/hooks/band.tsx
name: a reset kept window vanishes before the first reply
expect: (fail) terminal: the kept limits stand in before the first reply
<<<<<<< OLD
  if (!replied) {
    return kept
  }
======= NEW
  if (!replied) {
    return kept.filter(r => !hasReset(r, now))
  }
>>>>>>> END

name: an idle band reads every 12 hours again
expect: (fail) an idle band reads the figures every 5 minutes
<<<<<<< OLD
const USAGE_IDLE = 5 * 60_000
======= NEW
const USAGE_IDLE = 12 * 3600_000
>>>>>>> END

name: the usage read ignores the windows
expect: (fail) the usage windows are read into the store
<<<<<<< OLD
        await $.store.set('limitsStatus', await keepWindows($, body, now))
======= NEW
        await $.store.set('limitsStatus', 'skipped')
>>>>>>> END

name: a window set to null stays
expect: (fail) the usage windows are read into the store
<<<<<<< OLD
      got.delete(kind)
======= NEW
      void kind
>>>>>>> END

name: an older read overwrites a newer reply
expect: (fail) a read asked before a reply does not overwrite it
<<<<<<< OLD
  if (num(at) && at > asked) {
======= NEW
  if (false) {
>>>>>>> END

name: a reply's figures go undated
expect: (fail) the kept limits follow what the session reports
<<<<<<< OLD
      await $.store.set('limits', e.rateLimits)
      await $.store.set('limitsAt', await $.clock.now())
======= NEW
      await $.store.set('limits', e.rateLimits)
>>>>>>> END

name: fresh kept limits draw faint
expect: (fail) desktop: fresh kept limits are not drawn faint
<<<<<<< OLD
    const old = !own.length && !(num(keptAt) && Math.abs(now - keptAt) < LIMITS_FRESH)
======= NEW
    const old = !own.length
>>>>>>> END

name: the cache timer forgets a restart
expect: (fail) terminal: the cache timer survives a restart
<<<<<<< OLD
    const stored = (await read($, cacheAt))
      || asTimes(await $.store.get(CACHE_STORE))[await $.session.id().catch(() => '')]
======= NEW
    const stored = (await read($, cacheAt))
>>>>>>> END

name: another chat's cache time stands in
expect: (fail) terminal: the cache timer survives a restart
<<<<<<< OLD
      || asTimes(await $.store.get(CACHE_STORE))[await $.session.id().catch(() => '')]
======= NEW
      || Object.values(asTimes(await $.store.get(CACHE_STORE)))[0]
>>>>>>> END

@@@ mods/asdev/hooks/compaction.ts
name: a reply's cache time is not kept for a restart
expect: (fail) terminal: the cache timer counts down from the last reply
<<<<<<< OLD
      const id = await $.session.id().catch(() => '')
      if (id) {
======= NEW
      const id = await $.session.id().catch(() => '')
      if (false) {
>>>>>>> END

@@@ mods/asdev/hooks/compaction.ts
name: the first note ignores where the chat started
expect: (fail) the first note comes 100k past where the chat started
<<<<<<< OLD
  return Math.min((base || START_UNKNOWN) + FIRST_GAP, CAREFUL_FROM)
======= NEW
  return Math.min(START_UNKNOWN + FIRST_GAP, CAREFUL_FROM)
>>>>>>> END

name: a chat that starts big is first asked past 230k
expect: (fail) the first note comes 100k past where the chat started
<<<<<<< OLD
  return Math.min((base || START_UNKNOWN) + FIRST_GAP, CAREFUL_FROM)
======= NEW
  return (base || START_UNKNOWN) + FIRST_GAP
>>>>>>> END

name: every reply measures the start again
expect: (fail) the first note comes 100k past where the chat started
<<<<<<< OLD
      if (how) await update($, measureBase, () => '')
======= NEW
      void how
>>>>>>> END

name: a compaction keeps the old start
expect: (fail) the first note comes 100k past where the chat started
<<<<<<< OLD
    const how = e.source === 'compact' || e.source === 'clear' ? 'now'
======= NEW
    const how = e.source === 'clear' ? 'now'
>>>>>>> END

name: the start is not kept for a restart
expect: (fail) the first note comes 100k past where the chat started
<<<<<<< OLD
          await $.store.set(BASE_STORE, { ...Object.fromEntries(kept), [id]: tokens })
======= NEW
          void kept
>>>>>>> END

name: a reopened chat is measured again
expect: (fail) a reopened chat keeps the start it had
<<<<<<< OLD
      : e.source === 'startup' && !(await storedBase($, await $.session.id().catch(() => ''))) ? 'if-new' : ''
======= NEW
      : e.source === 'startup' ? 'now' : ''
>>>>>>> END

name: a compaction that never finished measures the start
expect: (fail) a compaction that never finished keeps the start
<<<<<<< OLD
      await update($, docsAt, () => 0)
      // The compacted session reloads
======= NEW
      await update($, docsAt, () => 0)
      await update($, measureBase, () => 'now')
      // The compacted session reloads
>>>>>>> END

name: a chat reopened with no start kept is measured at its size now
expect: (fail) a chat reopened with no start kept keeps the old 150k
<<<<<<< OLD
      if (how === 'now' || (how === 'if-new' && await isNewChat($))) {
======= NEW
      if (how) {
>>>>>>> END

name: /clear keeps the last chat's nudge mark
expect: (fail) /clear and a resume start afresh
<<<<<<< OLD
    if (e.source === 'clear' || e.source === 'resume') {
      await update($, nudgedAt, () => 0)
======= NEW
    if (e.source === 'clear' || e.source === 'resume') {
>>>>>>> END

name: /clear keeps the last chat's docs mark and lifts the hold
expect: (fail) past 280k with the docs not updated since 230k
<<<<<<< OLD
      await update($, nudgedAt, () => 0)
      await update($, docsAt, () => 0)
    }
======= NEW
      await update($, nudgedAt, () => 0)
    }
>>>>>>> END

name: a resume keeps the start this process measured last
expect: (fail) /clear and a resume start afresh
<<<<<<< OLD
    if (how || e.source === 'resume') await update($, contextBase, () => 0)
======= NEW
    if (how) await update($, contextBase, () => 0)
>>>>>>> END

name: the start is lost on a restart
expect: (fail) a reopened chat keeps the start it had
<<<<<<< OLD
  const base = (await read($, contextBase)) || await storedBase($, await $.session.id().catch(() => ''))
======= NEW
  const base = await read($, contextBase)
>>>>>>> END

name: the trigger line compacts before the chat's own threshold
expect: (fail) a reopened chat keeps the start it had
<<<<<<< OLD
  if (tokens < await compactFrom($)) return false
======= NEW
  if (tokens < START_UNKNOWN + FIRST_GAP) return false
>>>>>>> END
