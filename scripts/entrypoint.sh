#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
TASK="${H3_TASK:-ref2va}"
case "$TASK" in
  ref2va|fl2va) ;;
  *) echo "error: H3_TASK must be ref2va or fl2va (got $TASK)" >&2; exit 1 ;;
esac
"${ROOT}/check-weights.sh" /opt/ComfyUI/models --task "$TASK"

cd /opt/ComfyUI
if [[ -x /opt/nvidia/nvidia_entrypoint.sh ]]; then
  exec /opt/nvidia/nvidia_entrypoint.sh python main.py --listen 0.0.0.0 --port 8188 \
    --fast fp8_matrix_mult --disable-pinned-memory
fi
exec python main.py --listen 0.0.0.0 --port 8188 \
  --fast fp8_matrix_mult --disable-pinned-memory
