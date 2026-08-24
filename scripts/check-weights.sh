#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

usage() {
  echo "usage: check-weights.sh <weights-dir> [--task ref2va|fl2va|all]" >&2
  exit 1
}

DIR=""
TASK="${H3_TASK:-ref2va}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --task)
      TASK="${2:-}"; shift 2 ;;
    -h|--help)
      usage ;;
    *)
      if [[ -z "$DIR" && "$1" != --* ]]; then
        DIR="$1"; shift
      else
        usage
      fi ;;
  esac
done
[[ -n "$DIR" ]] || usage
case "$TASK" in
  ref2va|fl2va|all) ;;
  *) echo "error: unknown --task $TASK" >&2; exit 1 ;;
esac

lists=("$ROOT/required-weights-shared.txt")
case "$TASK" in
  ref2va) lists+=("$ROOT/required-weights-ref2va.txt") ;;
  fl2va) lists+=("$ROOT/required-weights-fl2va.txt") ;;
  all) lists+=("$ROOT/required-weights-ref2va.txt" "$ROOT/required-weights-fl2va.txt") ;;
esac

missing=0
for list in "${lists[@]}"; do
  while IFS= read -r rel || [[ -n "$rel" ]]; do
    [[ -z "$rel" || "$rel" == \#* ]] && continue
    if [[ ! -f "$DIR/$rel" ]]; then
      echo "MISSING $rel"
      missing=1
    fi
  done < "$list"
done
exit "$missing"
