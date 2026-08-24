#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENTRY="$ROOT/scripts/entrypoint.sh"

# missing file → fail
test -f "$ENTRY"

grep -q -- '--fast fp8_matrix_mult' "$ENTRY"
grep -q -- '--disable-pinned-memory' "$ENTRY"
# grep -v is NOT a "must not contain" check — it exits 0 if any line lacks the pattern.
if grep -E -- 'lowvram|novram|use-sage-attention|H3_LICENSE_ACK' "$ENTRY"; then
  echo "forbidden flag or license gate in entrypoint"; exit 1
fi
echo OK
