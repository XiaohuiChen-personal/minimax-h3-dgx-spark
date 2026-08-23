#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CHECK="$ROOT/scripts/check-weights.sh"

# missing script → fail the test runner if not implemented
test -x "$CHECK"

COMPLETE="$ROOT/tests/fixtures/weights-complete"
MISSING_DIT="$ROOT/tests/fixtures/weights-missing-dit"
DIT="diffusion_models/minimax_h3_fl2va_pruned_fp8_scaled.safetensors"
NON_DIT=(
  text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors
  vae/minimax_h3_video_vae_fp16.safetensors
  vae/minimax_h3_audio_vae_fp32.safetensors
  loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors
  upscale_models/SPAN2X
)

mkdir -p \
  "$COMPLETE/diffusion_models" \
  "$COMPLETE/text_encoders" \
  "$COMPLETE/vae" \
  "$COMPLETE/loras" \
  "$COMPLETE/upscale_models" \
  "$MISSING_DIT/diffusion_models" \
  "$MISSING_DIT/text_encoders" \
  "$MISSING_DIT/vae" \
  "$MISSING_DIT/loras" \
  "$MISSING_DIT/upscale_models"

touch "$COMPLETE/$DIT"
for rel in "${NON_DIT[@]}"; do
  touch "$COMPLETE/$rel" "$MISSING_DIT/$rel"
done
rm -f "$MISSING_DIT/$DIT"

# complete fixture
"$CHECK" "$COMPLETE"

# missing DiT — do NOT pipe the checker into grep under `set -o pipefail`.
# The checker exits 1 on purpose; a pipeline would fail the test even when correct.
if out="$("$CHECK" "$MISSING_DIT")"; then
  echo "expected failure on missing DiT"; exit 1
fi
printf '%s\n' "$out" | grep -q "MISSING $DIT"
echo OK
