#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
"${ROOT}/check-weights.sh" /opt/ComfyUI/models

cd /opt/ComfyUI
if [[ -x /opt/nvidia/nvidia_entrypoint.sh ]]; then
  exec /opt/nvidia/nvidia_entrypoint.sh python main.py --listen 0.0.0.0 --port 8188 \
    --fast fp8_matrix_mult --disable-pinned-memory
fi
exec python main.py --listen 0.0.0.0 --port 8188 \
  --fast fp8_matrix_mult --disable-pinned-memory
