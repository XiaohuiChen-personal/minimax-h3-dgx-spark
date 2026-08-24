#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CHECK="$ROOT/scripts/check-weights.sh"

test -x "$CHECK"

SHARED=(
  text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors
  vae/minimax_h3_video_vae_fp16.safetensors
  vae/minimax_h3_audio_vae_fp32.safetensors
  upscale_models/2x-spanx2-ch48.pth
)
REF2VA=(
  diffusion_models/minimax_h3_ref2va_pruned_fp8_scaled.safetensors
  loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors
)
FL2VA=(
  diffusion_models/minimax_h3_fl2va_pruned_fp8_scaled.safetensors
  loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors
)

FIX="$ROOT/tests/fixtures/weights-tasks"
rm -rf "$FIX"
for tree in complete-ref2va complete-fl2va complete-all missing-ref2va-dit missing-ref2va-lora; do
  mkdir -p "$FIX/$tree"/{diffusion_models,text_encoders,vae,loras,upscale_models}
done

touch_list() {
  local dest="$1"; shift
  local rel
  for rel in "$@"; do
    touch "$dest/$rel"
  done
}

touch_list "$FIX/complete-ref2va" "${SHARED[@]}" "${REF2VA[@]}"
touch_list "$FIX/complete-fl2va" "${SHARED[@]}" "${FL2VA[@]}"
touch_list "$FIX/complete-all" "${SHARED[@]}" "${REF2VA[@]}" "${FL2VA[@]}"
touch_list "$FIX/missing-ref2va-dit" "${SHARED[@]}" "${REF2VA[1]}" "${FL2VA[@]}"
touch_list "$FIX/missing-ref2va-lora" "${SHARED[@]}" "${REF2VA[0]}"

"$CHECK" "$FIX/complete-ref2va" --task ref2va
"$CHECK" "$FIX/complete-fl2va" --task fl2va
"$CHECK" "$FIX/complete-all" --task all

if out="$("$CHECK" "$FIX/complete-fl2va" --task ref2va)"; then
  echo "expected failure: fl2va tree is not enough for ref2va"; exit 1
fi
printf '%s\n' "$out" | grep -q "MISSING ${REF2VA[0]}"

if out="$("$CHECK" "$FIX/complete-ref2va" --task fl2va)"; then
  echo "expected failure: ref2va tree is not enough for fl2va"; exit 1
fi
printf '%s\n' "$out" | grep -q "MISSING ${FL2VA[0]}"

if out="$("$CHECK" "$FIX/complete-ref2va" --task all)"; then
  echo "expected failure: ref2va tree is not enough for --task all"; exit 1
fi
printf '%s\n' "$out" | grep -q "MISSING ${FL2VA[0]}"

if out="$("$CHECK" "$FIX/complete-fl2va" --task all)"; then
  echo "expected failure: fl2va tree is not enough for --task all"; exit 1
fi
printf '%s\n' "$out" | grep -q "MISSING ${REF2VA[0]}"

if out="$("$CHECK" "$FIX/missing-ref2va-dit" --task ref2va)"; then
  echo "expected failure on missing Ref2VA DiT"; exit 1
fi
printf '%s\n' "$out" | grep -q "MISSING ${REF2VA[0]}"

if out="$("$CHECK" "$FIX/missing-ref2va-lora" --task ref2va)"; then
  echo "expected failure on missing Ref2VA LoRA"; exit 1
fi
printf '%s\n' "$out" | grep -q "MISSING ${REF2VA[1]}"

# default task is ref2va (no --task, no H3_TASK). Later tasks export H3_TASK.
unset H3_TASK
"$CHECK" "$FIX/complete-ref2va"
if out="$("$CHECK" "$FIX/complete-fl2va")"; then
  echo "expected default task ref2va to reject fl2va-only tree"; exit 1
fi
printf '%s\n' "$out" | grep -q "MISSING ${REF2VA[0]}"

# --task overrides H3_TASK
if out="$(H3_TASK=fl2va "$CHECK" "$FIX/complete-fl2va" --task ref2va)"; then
  echo "expected --task ref2va to override H3_TASK=fl2va"; exit 1
fi
printf '%s\n' "$out" | grep -q "MISSING ${REF2VA[0]}"

# bare --task must usage, not a silent shift failure
if out="$("$CHECK" "$FIX/complete-ref2va" --task 2>&1)"; then
  echo "expected failure on bare --task"; exit 1
fi
printf '%s\n' "$out" | grep -q "usage:"

H3_TASK=fl2va "$CHECK" "$FIX/complete-fl2va"
echo OK
