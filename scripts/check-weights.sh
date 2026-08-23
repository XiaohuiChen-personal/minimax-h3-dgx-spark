#!/usr/bin/env bash
set -euo pipefail
DIR="${1:?usage: check-weights.sh <weights-dir>}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
LIST="$ROOT/required-weights.txt"
missing=0
while IFS= read -r rel || [[ -n "$rel" ]]; do
  [[ -z "$rel" || "$rel" == \#* ]] && continue
  if [[ ! -f "$DIR/$rel" ]]; then
    echo "MISSING $rel"
    missing=1
  fi
done < "$LIST"
exit "$missing"
