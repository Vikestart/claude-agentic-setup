#!/bin/sh
# Canonical launcher for Git Bash hooks.

audit_python="${AUDIT_PYTHON:-}"
if [ -z "$audit_python" ]; then
  if command -v python >/dev/null 2>&1; then
    audit_python="python"
  elif command -v python3 >/dev/null 2>&1; then
    audit_python="python3"
  elif command -v py >/dev/null 2>&1; then
    audit_python="py"
  else
    echo "Web audit unavailable: Python 3 not found (set AUDIT_PYTHON)." >&2
    exit 2
  fi
fi

PYTHONUTF8=1 "$audit_python" -X utf8 \
  "$(dirname "$0")/audit_all.py" "$@"
