#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SPEEDLOG="$SCRIPT_DIR/lib/speedlog.sh"
CHECK="$SCRIPT_DIR/check-weights.sh"
LIST="$SCRIPT_DIR/required-weights.txt"
LOG="$REPO_ROOT/measurements/download-log.md"

HF_REPO="Comfy-Org/MiniMax-H3"
SPAN_REL="upscale_models/2x-spanx2-ch48.pth"
SPAN_URL="https://objectstorage.us-phoenix-1.oraclecloud.com/n/ax6ygfvpvzka/b/open-modeldb-files/o/2x-spanx2-ch48.pth"

if [[ $# -ne 1 || -z "${1:-}" ]]; then
  echo "usage: download-weights.sh <dir>" >&2
  exit 1
fi

DIR="$1"

command -v hf >/dev/null || { echo "hf not installed; install huggingface_hub CLI"; exit 1; }

mkdir -p "$DIR"
DIR="$(cd "$DIR" && pwd)"

elapsed_seconds() {
  python3 - "$1" "$2" <<'PY'
import sys
start, end = float(sys.argv[1]), float(sys.argv[2])
secs = max(0.0, end - start)
if secs < 0.01:
    print(f"{secs:.4f}")
else:
    print(f"{secs:.2f}")
PY
}

within_1pct() {
  python3 - "$1" "$2" <<'PY'
import sys
actual, expected = int(sys.argv[1]), int(sys.argv[2])
if expected <= 0:
    raise SystemExit(1)
raise SystemExit(0 if abs(actual - expected) / expected <= 0.01 else 1)
PY
}

append_row() {
  "$SPEEDLOG" append "$LOG" "$1" "$2" "$3" "$4" "$5"
}

maybe_cache_hit() {
  local dest="$1" expected="$2"
  local actual
  if [[ -z "$expected" || "$expected" -le 0 ]]; then
    return 1
  fi
  if [[ ! -f "$dest" ]]; then
    return 1
  fi
  actual="$(stat -c%s "$dest")"
  if within_1pct "$actual" "$expected"; then
    echo "$actual"
    return 0
  fi
  return 1
}

expected_hf_bytes() {
  python3 - "$HF_REPO" "$@" <<'PY'
import sys
from huggingface_hub import HfApi

repo = sys.argv[1]
paths = sys.argv[2:]
infos = HfApi().get_paths_info(repo, paths, repo_type="model")
by_path = {info.path: int(info.size) for info in infos if getattr(info, "size", None) is not None}
for path in paths:
    print(f"{path}\t{by_path.get(path, 0)}")
PY
}

expected_span_bytes() {
  # Do not use `python3 - <<'PY'` on a pipe: `python3 -` reads the
  # program from stdin, so the heredoc eats the headers and
  # Content-Length is always missing (dest-present SPAN never skips).
  local headers
  headers="$(curl -sI "$SPAN_URL")"
  python3 - "$headers" <<'PY'
import sys

length = None
for raw in sys.argv[1].splitlines():
    line = raw.replace("\r", "")
    if line.lower().startswith("content-length:"):
        length = int(line.split(":", 1)[1].strip())
        break
if length is None:
    raise SystemExit(1)
print(length)
PY
}

fetch_hf() {
  local rel="$1"
  local dest="$DIR/$rel"
  local source="https://huggingface.co/${HF_REPO}"
  local expected="${HF_EXPECTED[$rel]:-0}"
  local cached bytes start end secs notes force=()

  if cached="$(maybe_cache_hit "$dest" "$expected")"; then
    append_row "$rel" "$source" "$cached" "0" "cache-hit"
    return 0
  fi

  if [[ -f "$dest" ]]; then
    force=(--force-download)
  fi

  echo "Downloading ${rel}"
  start="$(date +%s.%N)"
  hf download "$HF_REPO" "$rel" --local-dir "$DIR" "${force[@]}"
  end="$(date +%s.%N)"
  bytes="$(stat -c%s "$dest")"
  secs="$(elapsed_seconds "$start" "$end")"
  notes="hf download positional; stat bytes"
  if python3 -c "import sys; raise SystemExit(0 if float(sys.argv[1]) < 0.01 else 1)" "$secs"; then
    notes="cache-hit"
  fi
  append_row "$rel" "$source" "$bytes" "$secs" "$notes"
}

fetch_span() {
  local dest="$DIR/$SPAN_REL"
  local source="$SPAN_URL"
  local expected=0
  local cached bytes start end secs notes tmp

  expected="$(expected_span_bytes || true)"
  if cached="$(maybe_cache_hit "$dest" "$expected")"; then
    append_row "$SPAN_REL" "$source" "$cached" "0" "cache-hit"
    return 0
  fi

  mkdir -p "$(dirname "$dest")"
  tmp="${dest}.partial"
  echo "Downloading ${SPAN_REL}"
  start="$(date +%s.%N)"
  curl -fL --retry 5 --retry-delay 2 -o "$tmp" "$SPAN_URL"
  end="$(date +%s.%N)"
  mv -f "$tmp" "$dest"
  bytes="$(stat -c%s "$dest")"
  secs="$(elapsed_seconds "$start" "$end")"
  notes="OpenModelDB curl; stat bytes"
  if python3 -c "import sys; raise SystemExit(0 if float(sys.argv[1]) < 0.01 else 1)" "$secs"; then
    notes="cache-hit"
  fi
  append_row "$SPAN_REL" "$source" "$bytes" "$secs" "$notes"
}

hf_paths=()
while IFS= read -r rel || [[ -n "$rel" ]]; do
  [[ -z "$rel" || "$rel" == \#* ]] && continue
  if [[ "$rel" != "$SPAN_REL" ]]; then
    hf_paths+=("$rel")
  fi
done < "$LIST"

declare -A HF_EXPECTED=()
if ((${#hf_paths[@]} > 0)); then
  while IFS=$'\t' read -r path size; do
    HF_EXPECTED["$path"]="$size"
  done < <(expected_hf_bytes "${hf_paths[@]}")
fi

while IFS= read -r rel || [[ -n "$rel" ]]; do
  [[ -z "$rel" || "$rel" == \#* ]] && continue
  if [[ "$rel" == "$SPAN_REL" ]]; then
    fetch_span
  else
    fetch_hf "$rel"
  fi
done < "$LIST"

"$CHECK" "$DIR"
