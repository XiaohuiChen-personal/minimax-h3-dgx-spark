# `workflows/` — locked ComfyUI graphs

Empty on purpose until implementation. An implementing agent writes **exactly these two files** from this design. Do not add a third “experimental” graph in the first drop.

```text
workflows/
  h3-fl2va-smoke-5s17.json     # 960×544, 124 frames, 8 steps, SPAN 2×
  h3-fl2va-default-8s.json     # 960×544, 192 frames, 8 steps, SPAN 2×
```

Start from Comfy-Org’s T2V template, then lock our knobs:

https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_minimax_h3_t2v.json

## Nodes the graph must use

- `MiniMaxH3ImageToVideo` (or the current stock name for the same job) — prompt + optional `first_frame` / `last_frame`
- D-02 checkpoints only
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

Everything else stays locked. Do not put `<Picture N>` tags in the default prompt. Do not use `MiniMaxH3ReferenceToVideo`.

See [`../design/operator.md`](../design/operator.md) and [`../design/decisions.md`](../design/decisions.md).
