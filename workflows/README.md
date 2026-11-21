# `workflows/` — default ComfyUI graphs

Five **Turbo** graphs are the product defaults, plus an FL2VA **keyframe** graph, two optional no-Turbo **quality** Ref2VA graphs, and the two **fast** max-quality Ref2VA graphs that Claude Code uses by default (`.claude/skills/h3-make-video-fast/`). Use them as-is, copy and modify them, or add another API-format JSON when the use case needs it. Do not overwrite a shipped JSON unless the operator asked to change that default. One-off graphs go in a new filename. Do not ship a stock Comfy-Org UI-format template unchanged.

```text
workflows/
  h3-ref2va-smoke-5s17.json                 # default-task smoke: 960×544, length 124, 4 steps, SPAN 2×
  h3-ref2va-default-8s.json                 # default generate:   960×544, length 192, 4 steps, SPAN 2×
  h3-ref2va-long-15s08.json                 # optional long:      960×544, length 362, 4 steps, SPAN 2×
  h3-ref2va-quality-15s08-20step-1344.json  # optional quality:   1344×768, length 362, 20 steps, no Turbo / SPAN / FBC
  h3-ref2va-maxq-15s08-25step-1344.json     # max quality:        1344×768, length 362, 25 steps, beta, Sol-Attn off
  h3-ref2va-fast-15s08-672-span2x.json      # fast max quality:   672×384 (copy: 384×672), maxq knobs, refs match, SPAN 2× → 1344×768
  h3-ref2va-fast-locked-audio-15s08-672-span2x.json  # as above + a fixed soundtrack locked in (--soundtrack)
  h3-fl2va-smoke-5s17.json                  # text-only smoke:    960×544, length 124, 8 steps, SPAN 2×
  h3-fl2va-default-8s.json                  # text-only generate: 960×544, length 192, 8 steps, SPAN 2×
  h3-fl2va-keyframes-8s.json                # I2VA / FL2VA / L2VA: as above + LoadImage first_frame / last_frame
```

Prompts are H3's structured format, not one-liners: [`../design/prompting.md`](../design/prompting.md). The `prompt` strings committed in these files are placeholders; `--prompt-file` replaces them.

Default generate is **Ref2VA 8.00 s**. Snap “15 s” / “15.04 s” to `h3-ref2va-long-15s08.json` (**15.08 s / 362**, Turbo). Never invent **15.00** or **15.04**. Use the quality file only when the operator asked for no-Turbo / 20-step / 1344×768, and the max-quality file only when they asked for the best possible result and accept ~2 h 10 min. Claude Code's full video requests default to the fast pair below (~13 min). Text-only / no identity images uses the FL2VA pair.

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

- `MiniMaxH3ReferenceToVideo` — prompt + `ref_image_size=match`. Do **not** commit a `ref_images` dict (submit writes dotted `ref_images.ref_image_N` keys). No flat `ref_image_*` keys on this node
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

Everything else matches the quality graph: 1344×768, length 362, no Turbo LoRA, `res_multistep`, shifts **12 / 3**, `ref_image_size=max`, no FirstBlockCache, no EasyCache, no SPAN. Measured on this GB10 with six reference stills: **196.85 s/step**, **85.4 min** end to end (`Prompt executed in 01:25:24`). The default `--timeout` (3600 s) is too short; pass `--timeout 14400` (see the re-measurement below). First use: a two-bear snowy-courtyard clip where both characters matched their three-view stills. Use it only when the operator asks for the best possible result and accepts the wait; otherwise the 20-step quality graph is the no-Turbo default.

Re-measured 2026-11-17 with six ~1.5k px stills actually wired (the 85.4 min run above predates the dotted-keys fix, so its stills were silently dropped): **310 s/step**, **2 h 12 min** at 768×1344. Pass `--timeout 14400`.

## Ref2VA fast max quality (Claude Code default since 2026-11-17)

`h3-ref2va-fast-15s08-672-span2x.json` is the max-quality graph with three changes:

- **672×384** canvas (node `10`; set 384×672 on a copy for vertical). Token count drops from ~142k to ~33k with six stills, so attention cost falls ~19×.
- **`ref_image_size=match`**: stills scale down to the canvas area.
- **SPAN 2×** (`2x-spanx2-ch48.pth`) on the raw video VAE decode, then **`ImageSharpen`** (radius 1, sigma 1.0, alpha 0.1), then `CreateVideo`, so the mp4 is 1344×768 (or 768×1344). Measured 2026-11-17: a low-res render upscaled by SPAN alone had softer outlines than native (index 3.15 vs 3.52); the sharpen brings it to 3.60 with no visible halo. No `ImageScale` size lock: SPAN is exactly 2×, and a fixed lock would squash a vertical copy. `SaveVideo` stays at its default encoding (CRF 16 tripled the file with no sharpness gain).

Everything else is the maxq graph: no Turbo LoRA, 25 steps, `res_multistep` + `beta`, shifts 12 / 3, Sol-Attn off, no FBC / EasyCache. Measured 2026-11-17 (six stills, 384×672, 15.08 s): **26.7 s/step**, about **12 min** sampling plus ~1 min load and decode; SPAN on 362 frames took 37 s as a separate job. Against the native 768×1344 render of the same story, SPAN of its own 384×672 downscale scored SSIM 0.981 with slightly crisper lines (edge gradient 246 vs 233). The operator watched both and chose the fast one.

`h3-ref2va-fast-locked-audio-15s08-672-span2x.json` adds a fixed soundtrack:

- `LoadAudio` titled `soundtrack` → `VAEEncodeAudio` (H3 audio VAE) → `SetLatentNoiseMask` with a `SolidMask` of **0** (keep every tick) → `LTXVConcatAVLatent` with node `10`'s empty AV latent → sampler. H3 pins the masked audio rows at the condition timestep, so it draws the picture to the sound.
- Length lives on node `50` (`PrimitiveInt`); node `52` computes the tick count `round(length * 40 / 24)` for the mask.
- `submit-prompt.py --soundtrack FILE.wav` uploads the file and fails before any upload unless it is PCM, 32 kHz, stereo and exactly `round(length/24*40)*800` samples. A shorter file would leave an unmasked tail for H3 to fill.
- Measured 2026-11-17: a dancer hopped on 19–20 of 20 beats; reactions landed within 0.1 s of their sound effects. The output audio is the soundtrack after a VAE round trip; replace it with the lossless mix (`mux_audio.py` in the fast skill).

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

## Ref2VA + an exact frame (`MiniMaxH3AddGuide`)

Use this when one clip needs both identity stills and an exact frame: the video must open on a given picture, or pass through one at a set time. It is the pattern of Comfy-Org's "MiniMax H3: Multiframe Reference" template. It needs the ComfyUI v0.46.0 pin (2026-11-20). No shipped graph has the node, so add it to a copy:

1. Pass the frame still as one more `--ref-image` (say it is the 7th, so `ref_image_6`, LoadImage node `30` in the shipped Ref2VA graphs). The text encoder only sees it as `<Picture 7>`; the guide alone is invisible to the prompt.
2. Add the node and route the guider through it:
   ```json
   "90": {"class_type": "MiniMaxH3AddGuide",
          "inputs": {"positive": ["10", 0], "vae": ["3", 0], "latent": ["10", 1], "image": ["30", 0], "frame_idx": 0}}
   ```
   and set node `14` (`BasicGuider`) `conditioning` to `["90", 0]`. `frame_idx` is a pixel frame (`round(seconds × 24)`; negative counts from the end). Chain one node per anchor. The image is cover-cropped to the canvas.
3. Prompt (official ref guide §2.2–§4): tag `[keyframe completion + reference generation]`; a standalone line `<Picture 7> is the first frame of [Shot 1]: …` describing what the still shows; `The shot begins exactly from <Picture 7>.` at the start of `[Shot 1]`; retention `<Picture 7> ([Shot 1] first frame): fully_preserved - …`.
4. `submit-prompt.sh` needs no change: `--ref-image` wires the LoadImage, and the guide reads the same node.

Measured 2026-11-20 on the fast locked-audio graph (384×672 → 768×1344, 8 stills, seeds 42 / 2026; `measurements/comfyui-v0.46-upgrade-2026-11-20.md`):
- frame 0 has the still's composition. It is regenerated, not pasted: MAE 10 against the cover-cropped still, slightly darker (mean red 69 vs 78), fewer fine details;
- a locked soundtrack stays locked (render audio vs WAV corr 0.98);
- speed is unchanged (8.4 s/step at 124 frames; 15.08 s with 8 stills ≈ 14.4 min).

## Free fields the submit script may patch

- text prompt (`--prompt-file` for the structured multi-line format)
- seed
- output filename
- optional `--ref-image` local files (Ref2VA only; uploaded via `POST /upload/image`)
- optional `--first-frame` / `--last-frame` local files (keyframe graphs only; uploaded and linked)
- `--soundtrack` local WAV (locked-audio graphs only; checked, uploaded, required there)

Canvas, steps, length, LoRA on/off, and extra nodes may change on a **copy** or a new file when the use case needs it. 3-view sheets are Ref2VA `--ref-image`, **not** `first_frame`. An exact frame plus identity stills is a Ref2VA copy with `MiniMaxH3AddGuide` (section above), not the FL2VA keyframe graph.

See [`../design/operator.md`](../design/operator.md) and [`../design/decisions.md`](../design/decisions.md).
