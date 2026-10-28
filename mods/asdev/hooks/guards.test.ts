import { expect, test } from 'claude-code/testing'
import type { On } from 'claude-code'

// Beneath the mod: a tool that always runs, a small context (no compaction notes), and files whose
// length the test sets.
// A file is a line count, or its exact text. What reached the tool beneath lands in `seen`.
function world(on: On, files: Record<string, number | string>, seen: any[] = []) {
  on('session.usage', async () => ({ value: { startedAt: 0, rateLimits: [], context: { tokens: 1000, window: 1_000_000 } } }) as never)
  on('session.cwd', async () => ({ value: '/p' }) as never)
  on('tool.call', async (_$, e) => { seen.push(e); return { result: 'ok' } as never })
  on('fs.read', async (_$, e) => {
    // The engine hands the path on in the platform's form (C:\p\big.php on Windows).
    const path = String((e as any).path).replace(/\\/g, '/')
    const n = Object.entries(files).find(([name]) => path.endsWith(name))?.[1]
    if (n === undefined) throw new Error(`ENOENT ${path}`)
    return { value: typeof n === 'string' ? n : Array.from({ length: n }, (_, i) => `line ${i}`).join('\n') } as never
  })
}

const bash = ($: any, command: string) =>
  $.tool.call({ tool: 'Bash', tool_use_id: `u${Math.random()}`, command })

test('a shell heredoc is refused, with Write as the way instead; near-misses run', async ($: any, on) => {
  world(on, {})
  for (const cmd of ["cat <<EOF\nx\nEOF", "python - <<'EOF'\nprint(1)\nEOF", 'cat <<-"END" > f\nx\nEND', 'git commit -F - << MSG\nm\nMSG']) {
    expect((await bash($, cmd)).deny).toContain('Write tool')
  }
  for (const cmd of ['grep "<<" notes.md', "grep -c '<<EOF' x.sh", 'cat <<< "one line"', 'echo $((1<<3))', 'echo $((1 << n))', 'git commit -F msg.txt']) {
    expect((await bash($, cmd)).deny).toBeUndefined()
  }
})

test('a suite runner piped into a filter is refused, with quiet.py instead; near-misses run', async ($: any, on) => {
  world(on, {})
  for (const cmd of ['pytest -q | tail -5', 'python "$HOME/.claude/install/verify.py" 2>&1 | grep FAIL', 'python ~/.claude/skills/asdev-web-audit/scripts/audit_all.py -q | tail -2', 'claude plugin test mods/asdev | grep pass', 'python test_setup.py | head', 'pytest | tee log', 'echo pipefail; pytest | tail', 'python -m pytest |& tail', 'timeout 300 python -m pytest -q | tail -3', 'uv run pytest | grep FAIL', 'cd x && FOO=1 pytest -q | head', 'time pytest -q | tail -1']) {
    expect((await bash($, cmd)).deny).toContain('quiet.py')
  }
  // Inside compound commands, and behind a path-qualified wrapper or a negation.
  for (const cmd of ['for d in a b; do python -m pytest $d | tail -3; done', 'if true; then python -m pytest | tail; fi', 'if false; then :; else pytest | tail; fi', 'cd skills && { python -m pytest | tail; }', '! python -m pytest | tail', '/usr/bin/env python -m pytest | tail', '$PY -m pytest | tail', '${PY} -m pytest | tail']) {
    expect((await bash($, cmd)).deny).toContain('quiet.py')
  }
  for (const cmd of ['pip show pytest | head -3', 'composer show phpunit/phpunit | grep versions', 'vendor/bin/phpunit --version | head -1', 'python falsify.py --help 2>&1 | grep only', 'python -c "import pytest; print(pytest.__version__)" | head -1', 'bash -o pipefail -c "pytest | tail"', 'python ~/.claude/skills/asdev-web-audit/scripts/code_map.py tests/test_crlf.py | head -40', 'pip install pytest | tail -1', 'python -m pytest --collect-only -q | wc -l', 'pytest --co -q | wc -l', 'npm view jest | head', 'echo ${HOME} | head -1', 'for d in a b; do pip show $d | head -2; done', 'if true; then python -m pytest --collect-only -q | wc -l; fi']) {
    expect((await bash($, cmd)).deny).toBeUndefined()
  }
  for (const cmd of ['set -o pipefail; pytest -q | tail -5', 'pytest -q || echo failed', 'git log | head', 'python quiet.py -- pytest -q', 'grep -c x f | head -1', 'pytest -q > log.txt', 'pytest -q; ls -t logs | head -1', 'grep -n budget install/test_setup.py | head', 'cat verify.py | wc -l']) {
    expect((await bash($, cmd)).deny).toBeUndefined()
  }
})

test('a whole read of a file over 1,000 lines is refused; a range, a small file or an image runs', async ($: any, on) => {
  // The two `*.txt` files end with a newline, as real files do: 1,000 lines is not 1,001.
  const lines = (n: number) => Array.from({ length: n }, (_, i) => `line ${i}\n`).join('')
  world(on, { '/p/big.php': 1001, '/p/small.php': 1000, '/p/big.png': 5000, '/p/full.txt': lines(1000), '/p/over.txt': lines(1001) })
  const read = (input: object) => $.tool.call({ tool: 'Read', tool_use_id: `u${Math.random()}`, ...input })
  const r = await read({ file_path: '/p/big.php' })
  expect(r.deny).toContain('1001 lines')
  expect(r.deny).toContain('code_map.py')
  expect((await read({ file_path: '/p/big.php', offset: 1, limit: 200 })).deny).toBeUndefined()
  expect((await read({ file_path: '/p/big.php', limit: 200 })).deny).toBeUndefined()
  expect((await read({ file_path: '/p/small.php' })).deny).toBeUndefined()
  expect((await read({ file_path: '/p/full.txt' })).deny).toBeUndefined()
  expect((await read({ file_path: '/p/over.txt' })).deny).toContain('1001 lines')
  expect((await read({ file_path: '/p/big.png' })).deny).toBeUndefined()
  expect((await read({ file_path: '/p/missing.php' })).deny).toBeUndefined()
})

test('an Agent call passing model is refused, whatever its type; one without model runs', async ($: any, on) => {
  world(on, {})
  const spawn = (input: object) => $.tool.call({ tool: 'Agent', tool_use_id: `u${Math.random()}`, prompt: 'x', description: 'x', ...input })
  expect((await spawn({ subagent_type: 'opus-medium-executor', model: 'sonnet' })).deny).toContain('without `model`')
  expect((await spawn({ subagent_type: 'sonnet-medium-executor', model: 'opus' })).deny).toBeDefined()
  expect((await spawn({ subagent_type: 'haiku-high-helper', model: 'sonnet' })).deny).toBeDefined()
  expect((await spawn({ subagent_type: 'opus-medium-executor' })).deny).toBeUndefined()
  expect((await spawn({ subagent_type: 'general-purpose', model: 'sonnet' })).deny).toContain('without `model`')
  expect((await spawn({ model: 'haiku' })).deny).toContain('the default agent')
  expect((await spawn({ subagent_type: 'general-purpose' })).deny).toBeUndefined()
})

test('a foreground wait loop is refused, with run_in_background and Monitor instead; others run', async ($: any, on) => {
  world(on, {})
  for (const cmd of ['until [ -f done ]; do sleep 5; done', 'while ! grep -q ok log; do sleep 10; done; tail log', 'timeout 300 bash -c "until curl -s x; do sleep 2; done"'.replace(/"/g, ''), 'for i in $(seq 30); do curl -s localhost:8080 && break; sleep 2; done']) {
    expect((await bash($, cmd)).deny).toContain('run_in_background')
  }
  const bg = await $.tool.call({ tool: 'Bash', tool_use_id: 'b', command: 'until [ -f done ]; do sleep 5; done', run_in_background: true })
  expect(bg.deny).toBeUndefined()
  for (const cmd of ['grep -c "until x sleep" notes.md', 'while read l; do echo $l; done < f', 'sleep 1', 'grep -c until a.ts; grep -c sleep a.ts', 'rg -n while.*sleep src/', 'while IFS= read -r u; do curl -s $u; sleep 1; done < urls.txt', 'for f in *.php; do php -l $f; sleep 1; done']) {
    expect((await bash($, cmd)).deny).toBeUndefined()
  }
})

test('cat of a whole file over 1,000 lines is refused, a relative path too; small files and pipes run', async ($: any, on) => {
  // `C:/d/huge.php` is found only once `/c/d/…` is read as drive C (unconverted it is `C:\c\d\…`).
  world(on, { '/p/big.php': 1001, '/p/small.php': 1000, 'C:/d/huge.php': 1001 })
  expect((await bash($, 'cat C:/p/big.php')).deny).toContain('1001 lines')
  expect((await bash($, 'cat /c/d/huge.php')).deny).toContain('1001 lines')
  expect((await bash($, 'cat "big.php"')).deny).toContain('code_map.py')
  for (const cmd of ['cat -n big.php', 'cat big.php 2>/dev/null']) {
    expect((await bash($, cmd)).deny).toContain('1001 lines')
  }
  for (const cmd of ['cat small.php', 'cat big.php | head -50', 'cat missing.php', 'cat a.php b.php']) {
    expect((await bash($, cmd)).deny).toBeUndefined()
  }
})

test('a Write over a CRLF file keeps CRLF; LF files, new files and Edit are left alone', async ($: any, on) => {
  const seen: any[] = []
  world(on, { '/p/win.php': 'a\r\nb\r\n', '/p/unix.php': 'a\nb\n', '/p/run.sh': 'a\r\nb\r\n' }, seen)
  const write = (file_path: string) => $.tool.call({ tool: 'Write', tool_use_id: `w${Math.random()}`, file_path, content: 'x\ny\r\nz\n' })
  // Said, so a Write meant to turn the file LF is not taken as done.
  expect(((await write('/p/win.php')).context ?? []).join('\n')).toContain('crlf.py --fix --lf')
  expect(seen.pop().content).toBe('x\r\ny\r\nz\r\n')
  expect((await write('/p/unix.php')).context ?? []).toEqual([])
  expect(seen.pop().content).toBe('x\ny\r\nz\n')
  await write('/p/new.php')
  expect(seen.pop().content).toBe('x\ny\r\nz\n')
  // A shell script must stay LF: a Write there may be the fix.
  await write('/p/run.sh')
  expect(seen.pop().content).toBe('x\ny\r\nz\n')
})

test('the PowerShell tool gets the same rules: wait loop, here-string, piped runner, whole Get-Content', async ($: any, on) => {
  world(on, { '/p/big.php': 1001 })
  const ps = (command: string) => $.tool.call({ tool: 'PowerShell', tool_use_id: `p${Math.random()}`, command })
  for (const cmd of ['while (-not (Test-Path x)) { Start-Sleep 5 }', 'do { Start-Sleep 5 } while (-not (Test-Path x))', 'do { $r = gh run view; Start-Sleep 5 } until ($r -match "done")', 'for ($i = 0; $i -lt 30; $i++) { if (Test-Path x) { break }; Start-Sleep 2 }', 'foreach ($u in $urls) {\n  if (iwr $u) { break }\n  Start-Sleep 2\n}', 'Write-Host x; while ($true) { if (Test-Path x) { break }; Start-Sleep 1 }', '$r = while ($true) { Start-Sleep 1 }', '$r=do { Start-Sleep 1 } until (Test-Path x)']) {
    expect((await ps(cmd)).deny).toContain('run_in_background')
  }
  for (const cmd of ["git commit -m @'\nmsg\n'@", '$m = @"\nmsg\n"@', '$m=@"\nx\n"@', "Set-Content f (@'\nx\n'@)", "# don't\n$m = @'\nx\n'@", "Invoke-RestMethod u -Body:@'\nx\n'@", "$a,@'\nx\n'@", "Write-Host a;@'\nx\n'@", "if ($x) {# don't\n$m = @'\nx\n'@\n}", "$x = 1}# it's\n$m = @'\nx\n'@"]) {
    expect((await ps(cmd)).deny).toContain('here-string')
  }
  // `A; if ($?) { B }` is the chaining this tool's own instructions give.
  for (const cmd of ['pytest | Select-Object -Last 5', 'python -m pip list; if ($?) { python -m pytest | Select-Object -Last 5 }', 'cmd /c "python -m pytest" | Select-Object -Last 5', '& $py -m pytest | Select-Object -Last 5']) {
    expect((await ps(cmd)).deny).toContain('quiet.py')
  }
  expect((await ps('Get-Content big.php')).deny).toContain('1001 lines')
  for (const cmd of ['Get-Content big.php -TotalCount 50', 'Start-Sleep 2', 'git log | Select-Object -First 3', 'Select-String -Path C:\\p\\test_setup.py -Pattern x | Select-Object -First 3', 'foreach ($f in $files) { php -l $f; Start-Sleep 1 }', 'Get-Content C:/x/do.txt -Tail 5; Start-Job { Start-Sleep 1 }', 'foreach ($x in $y) { if ($x) { break } }; Get-Date; Invoke-Command { Start-Sleep 1 }', 'Get-ChildItem C:/while/x; Start-Sleep 1', 'git config user.email "user@"\ngit log -1', 'Write-Host "mail me @"\nWrite-Host b', 'Write-Output user@"\nline two"', 'Write-Output while ($x) { Start-Sleep 1 }', "Write-Host 'a#b @'\nWrite-Host c", 'Write-Host a#b@"\nx"', 'if ($?) { git log | Select-Object -First 3 }', 'cmd /c "dir" | Select-Object -First 3', '& $py -m pip list | Select-Object -First 3', '$deps = Get-Content requirements.txt; $deps -match "pytest" | Select-Object -First 3', '$log -notmatch "test_guard.py" | Select-Object -Last 3']) {
    expect((await ps(cmd)).deny).toBeUndefined()
  }
})
