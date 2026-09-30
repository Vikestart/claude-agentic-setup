#!/bin/sh
# Canonical asdev-web-audit gate on the exact staged index (install as .git/hooks/pre-commit, chmod +x).
# Delegates to the ONE canonical scanner copy — never copy scanners into a project. Verify the
# delegation with: python $HOME/.claude/skills/asdev-web-audit/scripts/harness_parity.py
# ($HOME rather than ~ so the line also works pasted into PowerShell, where a native command
#  does not expand ~. The `sh ~/...` below is run by bash, where ~ is correct.)
# Bypass deliberately, and only after proving zero NEW findings with audit_delta.py, with:
#   git commit --no-verify   (say so in the commit message)
sh ~/.claude/skills/asdev-web-audit/scripts/run_audit.sh --staged || {
  echo ""
  echo "Commit blocked by audit findings above (git commit --no-verify to bypass)."
  exit 1
}
