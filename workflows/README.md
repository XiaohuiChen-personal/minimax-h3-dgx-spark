# `workflows/` — default ComfyUI graphs

Five **Turbo** graphs are the product defaults, plus an FL2VA **keyframe** graph and two optional no-Turbo **quality** Ref2VA graphs. Use them as-is, copy and modify them, or add another API-format JSON when the use case needs it. Do not overwrite a shipped JSON unless the operator asked to change that default. One-off graphs go in a new filename. Do not ship a stock Comfy-Org UI-format template unchanged.

```text
workflows/
  h3-ref2va-smoke-5s17.json                 # default-task smoke: 960×544, length 124, 4 steps, SPAN 2×
  h3-ref2va-default-8s.json                 # default generate:   960×544, length 192, 4 steps, SPAN 2×
  h3-ref2va-long-15s08.json                 # optional long:      960×544, length 362, 4 steps, SPAN 2×
  h3-ref2va-quality-15s08-20step-1344.json  # optional quality:   1344×768, length 362, 20 steps, no Turbo / SPAN / FBC
  h3-ref2va-maxq-15s08-25step-1344.json     # max quality:        1344×768, length 362, 25 steps, beta, Sol-Attn off
  h3-fl2va-smoke-5s17.json                  # text-only smoke:    960×544, length 124, 8 steps, SPAN 2×
  h3-fl2va-default-8s.json                  # text-only generate: 960×544, length 192, 8 steps, SPAN 2×
  h3-fl2va-keyframes-8s.json                # I2VA / FL2VA / L2VA: as above + LoadImage first_frame / last_frame
```

Prompts are H3's structured format, not one-liners: [`../design/prompting.md`](../design/prompting.md). The `prompt` strings committed in these files are placeholders; `--prompt-file` replaces them.

Default generate is **Ref2VA 8.00 s**. Snap “15 s” / “15.04 s” to `h3-ref2va-long-15s08.json` (**15.08 s / 362**, Turbo). Never invent **15.00** or **15.04**. Use the quality file only when the operator asked for no-Turbo / 20-step / 1344×768, and the max-quality file only when they asked for the best possible result and accept ~85 min. Text-only / no identity images uses the FL2VA pair.

`<Picture N>` and `MiniMaxH3ReferenceToVideo` belong on Ref2VA graphs. Do not put those tags or that node on an FL2VA graph.

All five Ref2VA graphs ship nine `LoadImage` titles `ref_image_0`…`ref_image_8`. `--ref-image` is variable **1–9**. Leftover `LoadImage` nodes stay unlinked `example.png` and are not in the SaveVideo DAG. Default committed prompts may mention `<Picture 1>`…`<Picture 6>` as the six-bird smoke example (N=6 of 9). Live Ref2VA smokes exist on this Spark: `$HOME/h3-output/smoke-ref2va-5s17_00001_.mp4` and `$HOME/h3-output/smoke-ref2va-15s08_00001_.mp4`. Do not commit the mp4s. SaveVideo adds `_00001_`. Never print `/opt/ComfyUI/output`.

## Ref2VA (default task)

Start from Comfy-Org’s R2V template, then **rebuild** — do not ship it unchanged. Lock API-format integers. Official Ref2V Turbo LoRA is **4-step**. Do not strap the FL2V 8-step LoRA onto these graphs.

| Stock R2V habits | This repo |
|---|---|
| Unchanged UI-format template | API format, D-15 FP8 DiT + 4-step Ref2V LoRA |
| Composite 3-view sheet as the product path | Per-still `--ref-image` + `<Picture N>` (1-based, upload order) |
| Invented 15.00 / 15.04 | Legal **15.08 s / 362** (or another `17n+5` length on a copy) |

Nodes the **Turbo** Ref2VA graphs must use:

- `MiniMaxH3ReferenceToVideo` — prompt + `ref_image_size=match`. Do **not** commit a `ref_images` dict (submit writes the nested dict). No flat `ref_image_*` keys on this node
- Nine `LoadImage` nodes titled `ref_image_0`…`ref_image_8`
- D-15 DiT + Ref2V 4-step LoRA; D-02 TE / VAEs; D-04 SPAN
- `ModelSamplingAV` — two clocks, shifts **12 / 3** (the Ref2V 4-step v0.1 LoRA was distilled at 12 / 3; see D-06)
- Sampler: Euler + simple, **4 steps** (request 5 sigma points — the grid includes the last zero)
- SageAttention 2.2 path, Sol-Attn `triton_ref` (`tau` 1.3, `dense_blocks` `0-2,-1`), FirstBlockCache `H3 Safe`
- Video VAE decode + audio VAE decode, SPAN 2×, Save mp4 with audio

## Ref2VA quality (optional, not the 15 s snap)

`h3-ref2va-quality-15s08-20step-1344.json` follows the official Comfy R2V quality knobs on this box: **20 steps**, **1344×768**, **no Turbo LoRA**, `res_multistep`, shifts **12 / 3**, `ref_image_size=max`, Sage 2.2 + Sol-Attn `triton_ref` (`dense_blocks` `0-2,-1`). **No** FirstBlockCache, **no** EasyCache, **no** SPAN (native 1344×768 out). Still the pruned FP8 Ref2VA DiT. Wall time on this GB10 is about **45 min** (`2707.79 s`). Do not strap the FL2V LoRA onto it. Do not “fix” it back to 4-step Turbo / 960×544 / SPAN unless the operator asked to leave the quality path.

Operator note: Turbo quality is acceptable on FL2VA (text-only or first-frame); keep **8 steps** there for smoother motion. For Ref2VA identity stills, prefer this Turbo-off file. Even then, monk parakeets (Quakers) can still drift toward a budgerigar-like parakeet prior. Full write-up: [`../measurements/turbo-vs-base.md`](../measurements/turbo-vs-base.md) §16.

## Ref2VA max quality (optional, slowest)

`h3-ref2va-maxq-15s08-25step-1344.json` is the quality graph with three changes:

- **25 steps** instead of 20. Comfy docs: prefer 20–25 steps when references must hold.
- **`beta` scheduler** instead of `simple`. Comfy-Org R2V template note: “`beta` or `normal` scheduler tends to outperform `simple` for reference-heavy prompts.”
- **Sol-Attn off** (`enabled: false`, other Sol inputs unchanged), so every block runs exact Sage 2.2 attention instead of the sparse approximation.

Everything else matches the quality graph: 1344×768, length 362, no Turbo LoRA, `res_multistep`, shifts **12 / 3**, `ref_image_size=max`, no FirstBlockCache, no EasyCache, no SPAN. Measured on this GB10 with six reference stills: **196.85 s/step**, **85.4 min** end to end (`Prompt executed in 01:25:24`). The default `--timeout` (3600 s) is too short; pass `--timeout 7200` or more (more again if a job is queued ahead). First use: a two-bear snowy-courtyard clip where both characters matched their three-view stills. Use it only when the operator asks for the best possible result and accepts the wait; otherwise the 20-step quality graph is the no-Turbo default.

## FL2VA (text-only / no identity images)

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

Nodes the FL2VA graphs must use:

- `MiniMaxH3ImageToVideo` — prompt + optional `first_frame` / `last_frame`. Default T2V JSONs omit those keys; add them on a copy when the use case is I2VA / FL2VA keyframes
- D-02 checkpoints only (Comfy-Org files, including the 8-step LoRA — not the template’s `lightx2v` URL)
- `ModelSamplingAV` — two clocks, shifts **12 / 3** (the FL2V 8-step v1.0 LoRA is the 544p file, distilled at 12 / 3; 6 / 3 is only for 768p LoRAs)
- Turbo LoRA: `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16` at strength 1.0
- Sampler: Euler + simple, **8 steps** (request 9 sigma points)
- SageAttention 2.2, Sol-Attn `triton_ref` (`tau` 1.3, `dense_blocks` `0-2,-1`), FirstBlockCache `H3 Safe`
- Video VAE decode + audio VAE decode, SPAN 2×, Save mp4 with audio

## FL2VA keyframes (I2VA / FL2VA / L2VA)

`h3-fl2va-keyframes-8s.json` is `h3-fl2va-default-8s.json` plus two unlinked `LoadImage` nodes titled `first_frame` and `last_frame`. `MiniMaxH3ImageToVideo.first_frame` / `last_frame` are **IMAGE sockets**, so a path string can never work there. `submit-prompt.sh --first-frame` / `--last-frame` uploads the still and links the titled `LoadImage` into the node. A keyframe you do not pass stays unlinked (`None`). The default T2V graphs have no titled `LoadImage`, so the flags fail-close there.

Prompt: start with the official alignment line ([`../design/prompting.md`](../design/prompting.md)). `<Picture 1>` is the first attached keyframe. A keyframe is a real frame of the shot. Identity sheets are Ref2VA `--ref-image`.

## Free fields the submit script may patch

- text prompt (`--prompt-file` for the structured multi-line format)
- seed
- output filename
- optional `--ref-image` local files (Ref2VA only; uploaded via `POST /upload/image`)
- optional `--first-frame` / `--last-frame` local files (keyframe graphs only; uploaded and linked)

Canvas, steps, length, LoRA on/off, and extra nodes may change on a **copy** or a new file when the use case needs it. 3-view sheets are Ref2VA `--ref-image`, **not** `first_frame`.

See [`../design/operator.md`](../design/operator.md) and [`../design/decisions.md`](../design/decisions.md).
