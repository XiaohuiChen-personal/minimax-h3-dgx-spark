#!/usr/bin/env bash
set -euo pipefail

speedlog_append() {
  local log="$1"
  local artifact="$2"
  local source="$3"
  local bytes="$4"
  local seconds="$5"
  local notes="$6"
  local when mib pct row

  when="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  read -r mib pct < <(
    python3 - "$bytes" "$seconds" <<'PY'
import sys

bytes_ = float(sys.argv[1])
secs = float(sys.argv[2])
if secs < 0.01:
    print("n/a n/a")
else:
    mib = bytes_ / secs / 1048576
    pct = (bytes_ / secs / 1e6) / 1000 * 100
    print(f"{mib:.1f} {pct:.1f}")
PY
  )

  row="| ${when} | ${artifact} | ${source} | ${bytes} | ${seconds} | ${mib} | ${pct} | ${notes} |"
  printf '%s\n' "$row" | tee -a "$log"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  if [[ "${1:-}" != "append" || $# -ne 7 ]]; then
    echo "usage: speedlog.sh append <log> <artifact> <source> <bytes> <seconds> <notes>" >&2
    exit 1
  fi
  speedlog_append "$2" "$3" "$4" "$5" "$6" "$7"
fi
