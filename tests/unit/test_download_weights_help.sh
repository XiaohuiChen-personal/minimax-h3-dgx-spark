#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="$ROOT/scripts/download-weights.sh"

test -x "$SCRIPT"

if out="$("$SCRIPT" 2>&1)"; then
  echo "expected failure with no args"; exit 1
fi
printf '%s\n' "$out" | grep -qi usage

if out="$("$SCRIPT" --task ref2va 2>&1)"; then
  echo "expected failure with --task and no dir"; exit 1
fi
printf '%s\n' "$out" | grep -qi usage
printf '%s\n' "$out" | grep -q -- '--task'

# Three argv words. A usage-only stub (updated banner, still `$# -ne 1`)
# prints usage here and never names the bad value.
if out="$("$SCRIPT" /tmp --task not-a-task 2>&1)"; then
  echo "expected failure with unknown --task"; exit 1
fi
printf '%s\n' "$out" | grep -q 'unknown --task'
echo OK
