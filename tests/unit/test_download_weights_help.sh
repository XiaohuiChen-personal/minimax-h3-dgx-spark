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
echo OK
