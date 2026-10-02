// "Truthful state" (CLAUDE.shared.md §2), enforced at the stop: a reply that says the work was pushed,
// merged or deployed while the repo still has commits its upstream lacks is sent back once to
// check. Mined 2026-10-02: 1,467 such claims, and the owner caught one that was false.

const CLAIM = /\b(pushed|merged|deployed)\b/gi
// "not pushed", "isn't merged", "never deployed", "unpushed": the reply already says it is not done.
const NEGATED = /(\bnot|n't|\bnever|\bun|\bwithout)\W*(\w+\W+){0,2}$/i

type Run = (argv: string[]) => Promise<{ exitCode: number; stdout: string }>

export function claimsShipped(answer: string): boolean {
  for (const m of answer.matchAll(CLAIM)) {
    const before = answer.slice(Math.max(0, (m.index ?? 0) - 30), m.index)
    if (!NEGATED.test(before)) return true
  }
  return false
}

// The block reason, or nothing when the claim may stand (no claim, no repo, no upstream, nothing ahead).
export async function unpushed(answer: string, cwd: string, run: Run): Promise<string | undefined> {
  if (!claimsShipped(answer)) return undefined
  let head = ''
  try {
    const r = await run(['git', '-C', cwd, 'status', '-sb', '--porcelain=v1'])
    if (r.exitCode !== 0) return undefined
    head = r.stdout.split('\n')[0]
  } catch {
    // No git, or not a repo: nothing to hold the claim against.
    return undefined
  }
  const m = /^## (\S+?)\.\.\.(\S+) \[ahead (\d+)/.exec(head)
  if (!m) return undefined
  return `Your reply says the work was pushed, merged or deployed, but ${m[1]} in ${cwd} is ${m[3]} `
    + `commit(s) ahead of ${m[2]}: they are not on the remote. Check, then push or correct the reply.`
}
