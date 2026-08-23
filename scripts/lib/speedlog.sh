#!/usr/bin/env bash
set -euo pipefail

speedlog_append() {
  local log="$1"
  local artifact="$2"
  local source="$3"
  local bytes="$4"
  local seconds="$5"
  local notes="$6"
  local when mib pct row rates
  # Default field split even if a caller sourced us with a custom IFS.
  local IFS=$' \t\n'

  when="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  # Do not write `local rates="$(python3 …)" || return` — `local` hides python's status.
  rates="$(
    python3 - "$bytes" "$seconds" <<'PY'
import sys

bytes_ = float(sys.argv[1])
secs = float(sys.argv[2])
if secs < 0.01:
    print("n/a n/a")
else:
    # MiB/s uses 1048576; % of 1000 MB/s uses decimal MB vs 1e9 B/s (100 → 10.5, not 100).
    mib = bytes_ / secs / 1048576
    pct = (bytes_ / secs / 1e6) / 1000 * 100
    print(f"{mib:.1f} {pct:.1f}")
PY
  )" || return 1
  read -r mib pct <<<"$rates"
  if [[ -z "${mib}" || -z "${pct}" ]]; then
    echo "speedlog: failed to compute rates from bytes=${bytes} seconds=${seconds}" >&2
    return 1
  fi

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
