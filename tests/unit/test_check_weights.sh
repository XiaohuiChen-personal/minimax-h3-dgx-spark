#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CHECK="$ROOT/scripts/check-weights.sh"

# missing script → fail the test runner if not implemented
test -x "$CHECK"

# complete fixture
"$CHECK" "$ROOT/tests/fixtures/weights-complete"

# missing DiT — do NOT pipe the checker into grep under `set -o pipefail`.
# The checker exits 1 on purpose; a pipeline would fail the test even when correct.
if out="$("$CHECK" "$ROOT/tests/fixtures/weights-missing-dit")"; then
  echo "expected failure on missing DiT"; exit 1
fi
printf '%s\n' "$out" | grep -q 'MISSING diffusion_models/minimax_h3_fl2va_pruned_fp8_scaled.safetensors'
echo OK
