#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENTRY="$ROOT/scripts/entrypoint.sh"
COMPOSE="$ROOT/deploy/compose.yaml"
DOCKERFILE="$ROOT/deploy/Dockerfile"

# missing file → fail
test -f "$ENTRY"
test -f "$COMPOSE"
test -f "$DOCKERFILE"

grep -q -- '--fast fp8_matrix_mult' "$ENTRY"
grep -q -- '--disable-pinned-memory' "$ENTRY"
# grep -v is NOT a "must not contain" check — it exits 0 if any line lacks the pattern.
if grep -E -- 'lowvram|novram|use-sage-attention|H3_LICENSE_ACK' "$ENTRY"; then
  echo "forbidden flag or license gate in entrypoint"; exit 1
fi

# Compose default matches the entrypoint. No whole-tree weight volume.
grep -Fq 'H3_TASK: ${H3_TASK:-ref2va}' "$COMPOSE"
if grep -E -- ':/opt/ComfyUI/models:' "$COMPOSE"; then
  echo "whole-tree models volume"; exit 1
fi
# Image build must fail-close if the 15.08 graph is missing.
grep -Fq 'h3-ref2va-long-15s08.json' "$DOCKERFILE"

# Reject all / typos on the real start script (exits before check-weights / ComfyUI).
if out="$(H3_TASK=all "$ENTRY" 2>&1)"; then
  echo "expected H3_TASK=all to fail"; exit 1
fi
printf '%s\n' "$out" | grep -q 'H3_TASK must be ref2va or fl2va (got all)'
if printf '%s\n' "$out" | grep -q 'MISSING'; then
  echo "H3_TASK=all reached the weight checker"; exit 1
fi

if out="$(H3_TASK=typo "$ENTRY" 2>&1)"; then
  echo "expected H3_TASK=typo to fail"; exit 1
fi
printf '%s\n' "$out" | grep -q 'got typo'

# Accepted tasks: run only the prefix through check-weights, with a mock checker.
WORKDIR=$(mktemp -d)
trap 'rm -rf "$WORKDIR"' EXIT
awk '/check-weights\.sh/{print; exit} {print}' "$ENTRY" > "$WORKDIR/gate.sh"
if grep -q 'main.py' "$WORKDIR/gate.sh"; then
  echo "gate extract included ComfyUI launch"; exit 1
fi
tail -n 1 "$WORKDIR/gate.sh" | grep -q 'check-weights.sh'
cat > "$WORKDIR/check-weights.sh" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" > "$(dirname "$0")/check-args.txt"
exit 0
EOF
chmod +x "$WORKDIR/check-weights.sh"

unset H3_TASK
bash "$WORKDIR/gate.sh"
got=$(cat "$WORKDIR/check-args.txt")
if [[ "$got" != '/opt/ComfyUI/models --task ref2va' ]]; then
  echo "expected default --task ref2va, got: $got"; exit 1
fi

H3_TASK=fl2va bash "$WORKDIR/gate.sh"
got=$(cat "$WORKDIR/check-args.txt")
if [[ "$got" != '/opt/ComfyUI/models --task fl2va' ]]; then
  echo "expected --task fl2va, got: $got"; exit 1
fi

echo OK
