@@@ mods/asdev/hooks/guards.ts
name: a heredoc runs
expect: (fail) a shell heredoc is refused
<<<<<<< OLD
  if (ps ? /@['"][ \t]*\r?\n/.test(cmd) : hasHeredoc(cmd)) {
======= NEW
  if (ps ? /@['"][ \t]*\r?\n/.test(cmd) : false) {
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
    const before = cmd.slice(at + cut,
======= NEW
    const before = cmd.slice(at,
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

@@@ mods/asdev/hooks/guards.ts

name: a line range of a big file is refused too
expect: (fail) a whole read of a file over 1,000 lines is refused
<<<<<<< OLD
  if (!path || input.offset !== undefined || input.limit !== undefined || NOT_TEXT.test(path)) return undefined
======= NEW
  if (!path || NOT_TEXT.test(path)) return undefined
>>>>>>> END

name: model passes on a setup definition
expect: (fail) an Agent call passing model to a setup definition is refused
<<<<<<< OLD
  if (input.model === undefined || !DEFINITION.test(type)) return undefined
======= NEW
  return undefined
>>>>>>> END

name: model is refused on any agent type
expect: (fail) an Agent call passing model to a setup definition is refused
<<<<<<< OLD
  if (input.model === undefined || !DEFINITION.test(type)) return undefined
======= NEW
  if (input.model === undefined) return undefined
>>>>>>> END

@@@ mods/asdev/hooks/band.tsx
name: the band hides before the first context figure
expect: (fail) terminal: the band stays up before the first context figure
<<<<<<< OLD
    const { context, cost, rateLimits } = await $.session.usage()
======= NEW
    const { context, cost, rateLimits } = await $.session.usage()
    if (context.tokens === undefined) return next(e)
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
  return (context.tokens ?? 0) >= TRIGGER_FROM
======= NEW
  return true
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

@@@ mods/asdev/hooks/guards.ts

name: a reader naming a test file counts as a runner
expect: (fail) a suite runner piped into a filter is refused
<<<<<<< OLD
RUNNER.test(before) && !READER.test(before) &&
======= NEW
RUNNER.test(before) &&
>>>>>>> END

@@@ mods/asdev/hooks/guards.ts

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

name: inline code naming a runner is refused
expect: (fail) a suite runner piped into a filter is refused
<<<<<<< OLD
.replace(INLINE_CODE, ' ')
======= NEW
.replace(INLINE_CODE, '$&')
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

@@@ mods/asdev/hooks/compaction.ts

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
