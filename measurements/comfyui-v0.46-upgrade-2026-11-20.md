# ComfyUI pin moved to v0.46.0 (2026-11-20)

**Why:** the operator asked to upgrade to ComfyUI 0.34.0+ so the Ref2VA + `MiniMaxH3AddGuide` multiframe workflow (Comfy-Org template "MiniMax H3: Multiframe Reference", documented for 0.34.0+) runs on a documented version.

**Which version.** The H3 code at `v0.34.0` (`12d52794`, 2026-08-25) is byte-identical to the old pin `b78cec87` (0.33.0): `git diff b78cec87 v0.34.0 -- comfy/ldm/minimax comfy_extras/nodes_minimax_h3.py comfy/text_encoders/minimax.py comfy/model_base.py` is empty. Moving to v0.34.0 would only change the version string. The pin went to the latest release, **`v0.46.0` = `a277b5bf213e8a44fa34817b7770b54f86ef4cea`** (2026-11-18), which carries every upstream H3 fix since August, among them:

- `fc584aaa` VAE tile blend (was our backport patch; the patch is removed);
- `421a1c24` denoise-mask velocity scaling (masked rows; our locked audio uses mask 0, where nothing changes);
- `912fca4f` VAE rms_rope crash fix, `b2e31e89` / `f14bbe28` VAE memory, `2d6b7328` lower peak VRAM;
- `MiniMaxH3AddGuide` and `MiniMaxH3ReferenceToVideo` are unchanged apart from optional VAE inputs.

Checked before building:
- KJNodes `PathchSageAttentionKJ` still wins: v0.46 `wrap_attn` applies `transformer_options["optimized_attention_override"]` before the new `preferred_attention`.
- Sol-Attn wraps its imports in try/except; inside the new container `sol_attn` and `PackedLayout` both import (no silent fallback).
- Launch flags `--fast fp8_matrix_mult --disable-pinned-memory` exist in v0.46 `cli_args.py`.

## Build (Spark, `docker compose -f deploy/compose.yaml build`)

| Item | Value |
|---|---|
| Wall clock | 231 s |
| ComfyUI.git clone | 74,847,541 B in 3.45 s |
| SageAttention 2.2.0 wheel build | 75.9 s (`TORCH_CUDA_ARCH_LIST=12.0`, no sageattn3) |
| torchaudio 2.9.0 build | 80.1 s |
| torch | `2.10.0a0+b4e4ee81d3.nv25.12` (NGC, kept) |
| comfy-kitchen / comfy-aimdo | 0.2.41 / 0.6.0 |
| Tile-blend regression test (now against upstream code) | max error 2.7e-15 / 5.3e-15 / 5.3e-15 at 544x960 / 768x1344 / 960x544 |
| Image | `h3-spark:local` = `sha256:64cb4fd6…`; old image kept as `h3-spark:b78cec87-0.33.0` for rollback |

## After the restart

- `/system_stats`: `comfyui_version` 0.46.0, GB10 `cuda:0`.
- Custom nodes: KJNodes, sol-attn, FirstBlockCache imported (no `IMPORT FAILED`).
- All 12 shipped workflows plus the guide graph validate against `/object_info`: every `class_type` exists, every input name is known, no required input missing.
- `watch_progress.py` (websocket progress + `/history`) works unchanged.

## Live pilot: Ref2VA + AddGuide (frame 0) + locked soundtrack, fast graph

Copy of `h3-ref2va-fast-locked-audio-15s08-672-span2x.json`, 384x672 → SPAN 768x1344, 124 frames (5.17 s), 8 stills (`match`), `MiniMaxH3AddGuide` at `frame_idx` 0 fed from the `ref_image_6` LoadImage (the same still is `<Picture 7>`), seed 42, prompt tagged `[keyframe completion + reference generation]`.

| Check | Result |
|---|---|
| Speed | 8.4 s/step measured; the FLOPs formula (`h3-gb10-throughput`, N ≈ 14.6k) predicts 7.8 s/step: throughput unchanged |
| Wall clock | 287 s, including the first model load after the restart |
| Frame 0 vs the source still (cover-cropped to 768x1344) | same composition (alignment best at 0 px shift); MAE 10.3 / PSNR 24.1 dB; a half-res round trip alone gives MAE 2.5 / 34.0 dB, so the guide is regenerated, not pasted: slightly darker (mean R 69 vs 78), softer ground texture, fewer distant lights |
| Locked audio | render audio vs locked WAV corr 0.984 at lag 0 (H3 added no sound of its own); `mux_audio.py --expect-locked` → `MUX_OK` |
| Picture | both bears walked in from the bottom edge (back view) by 0.5 s and walked toward the moon, identity matches the three-view sheets from behind |

## Full clips on the new pin (《无限月读》, 2026-11-20)

Same graph at 362 frames (15.08 s), 8 stills (6 identity + the first-frame scene + a two-eye design crop), AddGuide frame 0, locked piano soundtrack, seeds 42 and 2026:

| Check | Result |
|---|---|
| Speed | 30.2 / 28.8 s/step; 863 s wall for seed 42 from submit to mp4 (formula N ≈ 34k) |
| Frame 0 | the user's scene still in both seeds; profile walk continued from it |
| Locked audio | render audio vs locked WAV corr 0.98, lag 0; `MUX_OK` with the lossless track |
| Reference leak | the eye-design still (`attribute_transfer`, Shot 3 only) never appeared before the reveal, nor on the second bear |
| Defects | seed 42 drew the ω plus a straight mouth for 3.35 s (fixed in post); both seeds opened the eyes on the G chord (11.7 s) rather than the prompted F chord (10.1 s) |
