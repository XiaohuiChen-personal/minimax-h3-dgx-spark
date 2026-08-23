#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
tmp=$(mktemp)
echo '| When (UTC) | Artifact | Source | Bytes | Seconds | MiB/s | % of 1000 MB/s | Notes |' > "$tmp"
echo '|---|---|---|---:|---:|---:|---:|---|' >> "$tmp"
"$ROOT/scripts/lib/speedlog.sh" append "$tmp" "probe.bin" "https://example.test" 104857600 1.0 "unit"
grep -q 'probe.bin' "$tmp"
grep -q '| 100.0 |' "$tmp"   # 100 MiB in 1 s = 100.0 MiB/s
grep -q '| 10.5 |' "$tmp"    # 104.8576 MB/s ÷ 1000 MB/s = 10.5%, not 100
"$ROOT/scripts/lib/speedlog.sh" append "$tmp" "cached.bin" "https://example.test" 104857600 0 "cache-hit"
grep -q 'n/a' "$tmp"
echo OK
