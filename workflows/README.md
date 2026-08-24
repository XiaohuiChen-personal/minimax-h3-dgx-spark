# `workflows/` — locked ComfyUI graphs

These two locked graphs are already in the tree. Do not add a third “experimental” graph. Do not rewrite them from the stock Comfy-Org template.

```text
workflows/
  h3-fl2va-smoke-5s17.json     # 960×544, length 124, 8 steps, SPAN 2×
  h3-fl2va-default-8s.json     # 960×544, length 192, 8 steps, SPAN 2×
```

Start from Comfy-Org’s T2V template, then **rebuild** — do not ship it unchanged:

https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_minimax_h3_t2v.json

That file is **UI format** (nodes/links/subgraph), not `POST /prompt` API format. Stock knobs are **not** this product:

| Stock template | This repo |
|---|---|
| `minimax_h3_fl2va_pruned_int8_convrot` + `qwen3vl_32b_minimax_h3_nvfp4_awq` | D-02 FP8 DiT + INT8 TE |
| 1344×768, `length` 73, 4 steps, `res_multistep` | 960×544, 124 or 192, 8 steps, Euler+simple |
| No SPAN / Sol-Attn / FBC / `ModelSamplingAV` | Add those |
| Node **id** 124 is `BasicScheduler` | Smoke **length** is 124; do not substring-test `"124"` |

Lock tests must parse API-format `inputs.length` / `inputs.steps` / `inputs.width`. Never `assert "192" not in raw` (`1920` contains `192`). Never treat `"192" in raw` as proof of 192 frames.

## Nodes the graph must use

- `MiniMaxH3ImageToVideo` (or the current stock name for the same job) — prompt + optional `first_frame` / `last_frame`. Lock `width` / `height` / `length` / `steps` as integer literals (no `ResolutionSelector`, no duration-math node)
- D-02 checkpoints only (Comfy-Org files, including the 8-step LoRA — not the template’s `lightx2v` URL)
- `ModelSamplingAV` — two clocks, shifts 6 / 3 with Turbo
- Turbo LoRA: `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16` at strength 1.0
- Sampler: Euler + simple, **8 steps** (request 9 sigma points — the grid includes the last zero)
- SageAttention 2.2 path (not the `--use-sage-attention` flag)
- Sol-Attn kernel **`triton_ref`**
- FirstBlockCache **`H3 Safe`**
- Video VAE decode + audio VAE decode
- SPAN 2× to 1920×1088, crop to 1920×1080
- Save mp4 with audio

## Free fields the submit script may patch

- text prompt
- seed
- output filename
- optional first/last-frame image paths

Everything else stays locked. Do not put `<Picture N>` tags in the default prompt. Do not use `MiniMaxH3ReferenceToVideo`. Keyframes are attached files; the VAE does not invent them.

See [`../design/operator.md`](../design/operator.md) and [`../design/decisions.md`](../design/decisions.md).
