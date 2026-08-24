# Turbo LoRA vs no-Turbo — live wall times on this GB10

Recorded 2026-08-24 on the Spark that hosts this repo. Times are ComfyUI `execution_success − execution_start` from `/history` unless noted. Host outputs stay under `$HOME/h3-output/`. Do not treat these as apples-to-apples quality scores — several knobs moved with the LoRA.

Shared launch: `main.py --listen 0.0.0.0 --port 8188 --fast fp8_matrix_mult --disable-pinned-memory`. Sage 2.2 + Sol-Attn `triton_ref` were on for every live generate below.

## What “Turbo on” means here

Product Ref2VA graphs use `minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors` at `strength_model=1.0`. Locked default is **4 steps**. Creative tries below also ran that same LoRA at **8 steps**. Canvas is **960×544**, Euler+simple, shifts **6 / 3**, FirstBlockCache `H3 Safe`, then SPAN 2× and crop to 1920×1080. FL2VA product graphs use the **8-step** FL2V Turbo LoRA on the same canvas.

## What “Turbo off” means here

Shipped quality graph: `workflows/h3-ref2va-quality-15s08-20step-1344.json`. The 8.00 s sibling used for v6 lived in `temp/` and was deleted with that folder. No `LoraLoaderModelOnly`, **20 steps**, **1344×768**, `res_multistep`, shifts **12 / 3**, `ref_image_size=max`, no FirstBlockCache, no EasyCache, no SPAN (native 1344×768 out). Still the pruned FP8 Ref2VA DiT. This is **not** Hailuo / MiniMax API 2K Omni Reference.

## Turbo on — this ComfyUI history

| Job | Task | Length | Steps | LoRA | Canvas | ComfyUI s | Clock |
|---|---|---|---|---|---|---|---|
| `smoke-ref2va-5s17` `f32b42ec` | Ref2VA, 6 bird stills | 5.17 s / 124 | 4 | Ref2V Turbo | 960×544 → SPAN | **133.02** | 2.2 min |
| `smoke-ref2va-15s08` `0db003d2` | Ref2VA, 6 bird stills | 15.08 s / 362 | 4 | Ref2V Turbo | 960×544 → SPAN | **374.04** | 6.2 min |
| `monk-oldmoney` `c35030bf` | Ref2VA 15.08 | 15.08 s / 362 | 4 | Ref2V Turbo | 960×544 → SPAN | **377.71** | 6.3 min |
| `monk-oldmoney-v2` `fbc986f6` | Ref2VA 15.08 | 15.08 s / 362 | 4 | Ref2V Turbo | 960×544 → SPAN | **368.79** | 6.1 min |
| `monk-oldmoney-v3` `01e17dd5` | Ref2VA 15.08 | 15.08 s / 362 | 4 | Ref2V Turbo | 960×544 → SPAN | **363.71** | 6.1 min |
| `monk-oldmoney-v4` `7d4f9183` | Ref2VA, 2 yard photos | 15.08 s / 362 | 8 | Ref2V Turbo | 960×544 → SPAN | **515.83** | 8.6 min |
| `monk-oldmoney-v5` `e9891b3b` | Ref2VA, 6 cropped 3-view stills, `ref_image_size=max` | 15.08 s / 362 | 8 | Ref2V Turbo | 960×544 → SPAN | **567.27** | 9.5 min |
| `yard-fight-8s` `aaf1b561` | FL2VA I2VA first-frame | 8.00 s / 192 | 8 | FL2V Turbo | 960×544 → SPAN | **284.58** | 4.7 min |

Sampler notes from logs (not a second clock):

- Ref2VA 5.17 / 4-step: `4/4 [00:39, 9.95s/it]` after model init.
- Ref2VA 15.08 / 4-step smoke: init **70.45 s**, then `4/4 [02:38, 39.70s/it]`.
- Ref2VA 15.08 / 8-step v4: `8/8 [05:25, 40.74s/it]`.
- Ref2VA 15.08 / 8-step v5: `8/8 [05:35, 41.94s/it]`.
- FL2VA I2VA 8.00: `8/8 [02:33, 19.22s/it]`.

## Turbo on — earlier FL2VA product smokes (`measurements/prereq.md`)

Not in the current `/history` window. Same box, same launch flags.

| Job | Task | Length | Steps | LoRA | ComfyUI s | Clock |
|---|---|---|---|---|---|---|
| `smoke-5s17` | FL2VA T2V | 5.17 s / 124 | 8 | FL2V Turbo | **190.08** | 3.2 min |
| `default-8s` | FL2VA T2V | 8.00 s / 192 | 8 | FL2V Turbo | **286.38** | 4.8 min |

FL2VA 8.00 sampler: init **28.47 s**, then `8/8 [02:39, 19.97s/it]`.

## Turbo still on, 20 steps — interrupted (do not treat as a finish time)

`bb553ec1`: Ref2VA **15.08 s / 362**, **20 steps**, **Ref2V Turbo still loaded**, 960×544, Euler. Interrupted at sampler **19/20**. Log: `Prompt executed in 582.55 seconds`. That is **not** the no-Turbo quality graph.

## Turbo off — finished

| Job | Task | Length | Steps | LoRA | Canvas | ComfyUI s | Clock |
|---|---|---|---|---|---|---|---|
| `monk-oldmoney-v6` `eea44df0` | Ref2VA, 2 whole 3-view sheets | 8.00 s / 192 | 20 | **none** | **1344×768**, no SPAN | **1103.65** | **18.4 min** |
| `monk-oldmoney-v8` `2b84d567` | Ref2VA, 2 yard side photos | 15.08 s / 362 | 20 | **none** | **1344×768**, no SPAN | **2707.79** | **45.1 min** |

Host v6: `$HOME/h3-output/monk-oldmoney-v6_00001_.mp4` (`1793449` B). `ffprobe`: **8.00 s**, **1344×768**, **192** frames, 24 fps, 32 kHz stereo. Sampler: first step **83.17 s** init, then `20/20 [15:58, 47.94s/it]`. Video VAE **09:00:42 → 09:02:21 ≈ 99.5 s**. No SPAN. Log: `Prompt executed in 00:18:23`. Sol-Attn tokens **60357**. Do not claim identity from the probe.

Host v8: `$HOME/h3-output/monk-oldmoney-v8_00001_.mp4` (`3467829` B). `ffprobe`: **15.08 s**, **1344×768**, **362** frames, 24 fps, 32 kHz stereo. Sampler: first step included init (**~203.6 s**), then `20/20 [40:29, 121.46s/it]`. Video VAE **09:54:56 → 09:58:02 ≈ 186 s**. No SPAN. Log: `Prompt executed in 00:45:07`. Sol-Attn token line did not reprint (already patched earlier in this ComfyUI process). Do not claim identity from the probe.

Per-step seconds on v6 look similar to 15.08 s × 960×544 on purpose: 8.00 s × 1344×768 is almost the same latent work. Pixel×frame ratio: `(1344×768×192)/(960×544×362) ≈ 1.05`. Sol-Attn tokens: v6 **60357** vs 15.08 Turbo **56364**. Turbo is not what sets `s/it`. v8 keeps the same 1344×768 canvas and **raises length to 362**, so `s/it` jumps: **121.46** vs v6 **47.94** (≈ **2.53×**; frame ratio **362/192 ≈ 1.89×**). Attention cost grows faster than linear in frames.

## How to read the gap

On this box, **Turbo 4-step Ref2VA 15.08 s** lands around **6.1–6.3 min**. Doubling to **8 Turbo steps** on the same length lands around **8.6–9.5 min**. **No-Turbo 20-step 8.00 s at 1344×768** finished in **18.4 min** (`1103.65 s`): ~16 min sampler + ~100 s video VAE, no SPAN. **No-Turbo 20-step 15.08 s at 1344×768** (v8) finished in **45.1 min** (`2707.79 s`): ~40.5 min sampler + ~186 s video VAE, no SPAN.

Headline: product Turbo Ref2VA 15 s is about **six minutes**; the 8 s quality graph was **18.4 minutes**; the 15.08 s quality graph was **45.1 minutes**. The 4-step vs 20-step gap is **step count**. The 8 s vs 15.08 s quality-graph gap is **length at the same 1344×768 canvas** (`s/it` and VAE both scale).

## VAE / SPAN after the sampler (this box)

From Comfy logs: last `N/N` tqdm → `Prompt executed`. Audio VAE is seconds. Video VAE then SPAN (product graphs only).

| Job class | Frames / canvas | Video VAE | SPAN | Sampler → done |
|---|---|---|---|---|
| Ref2VA 5.17 s Turbo | 124 / 960×544 | **~36 s** | **~29 s** | **~66 s** |
| Ref2VA 15.08 s Turbo (4 or 8 steps) | 362 / 960×544 | **~95 s** | **~82–92 s** | **~3.0 min** |
| FL2VA I2VA 8.00 s Turbo | 192 / 960×544 | **~50 s** | **~49 s** | **~100 s** |
| v6 no-Turbo | 192 / 1344×768, no SPAN | **~99.5 s** | **none** | **~100 s** (sampler 20/20 → `Prompt executed`) |
| v8 no-Turbo | 362 / 1344×768, no SPAN | **~186 s** | **none** | **~187 s** (sampler 20/20 → `Prompt executed`) |

v6 video VAE matched the 15.08 s 960×544 decode (~95 s), not the 8.00 s 960×544 decode (~50 s). Pixel×frame ratio predicted that. No SPAN after.

## Learnings (2026-08-24 session)

Operator notes from the monk-parakeet identity runs. Not a product change. Locked defaults stay D-15 / D-02.

1. **This Spark is not Hailuo / MiniMax API Omni Reference.** Reddit “awesome reference” clips are usually the official API (full H3, about 2K, ~20 steps, no Turbo). This box runs **pruned FP8 Ref2VA** + (product path) **4-step Ref2V Turbo** + **960×544 + SPAN**. Same family, different stack.

2. **Official Comfy R2V quality template is 20 steps, 1344×768, Turbo off.** That is the local quality path (`workflows/h3-ref2va-quality-15s08-20step-1344.json`; v6 used an 8.00 s copy that is no longer in the tree). It is still FP8, not API 2K.

3. **Turbo is a speed stack, not an identity stack.** On this GB10: 4-step Ref2VA 15.08 s ≈ **6.1–6.3 min**; same length at 8 Turbo steps ≈ **8.6–9.5 min**. v4 (2 yard photos, 8 Turbo steps) and v5 (6 cropped 3-view stills, `ref_image_size=max`, 8 Turbo steps) both finished and still failed the “same bird” test. See **16** for when Turbo is still worth using.

4. **Do not read a 20-step job as no-Turbo unless the LoRA node is gone.** `bb553ec1` was 20 steps **with** Ref2V Turbo still loaded on the 15.08 s 960×544 graph; interrupted at 19/20 after **582.55 s**.

5. **Ref2VA and first-frame FL2VA / I2VA are mutually exclusive.** Official API: first-frame and Omni Reference do not stack. `yard-fight-8s` locked the yard as `first_frame`; the yellow bird could only be text. `MiniMaxH3AddGuide` would pin a still onto a frame and break the shot.

6. **Ref2VA = up to 9 separate images, 1-based `<Picture N>`.** Official example is “appearance follows images 1 and 2.” There is **no** official rule that a 3-view sheet is required. A whole Front/Side/Back sheet as one image can copy the grid, the printed captions, and duplicate one bird. Product smokes used **six per-view stills**. v6 feeds **two whole sheets** on purpose (`<Picture 1>` blue, `<Picture 2>` yellow). Identity stills are `--ref-image`, not `first_frame`.

7. **H3 is CFG-distilled.** One `prompt`. No negative prompt. No `guidance_scale`. Speech on FL2VA is written in that same string. Quiet Ref2VA smokes stay room tone.

8. **Length snaps to `17n+5`.** Legal: 4.46 / 5.17 / 8.00 / 10.13 / 15.08 s. Never invent 10.00 / 15.00 / 15.04. Snap “15 s” to 15.08. There is no locked 10.13 s JSON in this repo.

9. **Do not strap the FL2V LoRA onto Ref2VA.** The package name `…turbo_4step…` is the file name even when the scheduler is 8 steps.

10. **Wall time and identity are different questions.** v6 finished in **18.4 min**. v8 finished in **45.1 min**. Do not claim the birds match until the operator watches the host mp4.

11. **Removing Turbo barely changes seconds per DiT step at the same latent size.** Turbo is a **fewer-steps** LoRA (4 instead of 20), not a cheaper forward. v6 `s/it` (~48 s) matches 15.08 s Turbo (~40–42 s) because those latents are almost the same size. The 4-vs-20 wall-time hit is `20 × ~48 s` vs `4 × ~40 s`. **Length at 1344×768 does change `s/it`:** v8 is **121.46 s/it** on 362 frames. VAE does not get a 20-step schedule; it is one decode after `20/20` (v6 ~99.5 s, v8 ~186 s; ratio ≈ 362/192).

12. **Sage 2.2 on this GB10 is a speed kernel, not the identity problem.** Kernel check (2026-08-23): SageAttention 2.2.0 vs SDPA at S=25120, cosine **1.000**, **1.62×**. Mode in the live graphs: `sageattn_qk_int8_pv_fp16_triton`. The documented quality failure is **Sage 3**, a blind `--use-sage-attention` flag, or the **~160k token** FP8-attention “pure noise” cliff — not a 2.2 vs SDPA look-alike test. v6 is **60357** tokens. This session did **not** A/B Sage on/off on a full clip. Do not turn Sage off on a running job.

13. **Ref2VA identity is not a VAE “subject lock” step.** Live node `MiniMaxH3ReferenceToVideo` (`/opt/ComfyUI/comfy_extras/nodes_minimax_h3.py`): each still is resized, then **both** `vae.encode(resized)` (video VAE → frozen `minimax_refs` image block) **and** RGB into Qwen3-VL (`clip.tokenize(..., minimax_ref_items=)` + `<Picture N>`). The empty AV latent is separate noise. There is no image-VAE. First-frame I2VA is the other path (`vae.encode` → `minimax_keyframes` pinned at frame 0). A 3-view sheet encoded as one image puts the grid into both Qwen and the ref latent; denoise can copy it; decode then shows that copy. Decode does not “re-encode” the refs.

14. **Not using [Mamad8/MiniMax-H3-Image-VAE](https://huggingface.co/Mamad8/MiniMax-H3-Image-VAE).** Host + live `/models/vae` + v6 graph load only `minimax_h3_video_vae_fp16.safetensors` (Comfy-Org, `5207808496` B) and `minimax_h3_audio_vae_fp32.safetensors`. Ref stills and video decode share that official video VAE. The Image-VAE card says images only; do not swap it into a video graph.

15. **v6 identity miss is budgerigar prior, not VAE mix-up.** Operator judged v6 much closer, then frame-sampled `monk-oldmoney-v6_00001_.mp4` (keys at 0 / 1.0 / 2.0 / 2.6 / 3.0 / 4.0 / 5.0 / 8.0 s). Blue bird shows wavy nape/wing bars and circular cheek spots in every sampled frame; yellow bird is milder but can pick up faint wing waves. The two 3-view sheets do not have those marks. H3 default parrot prior looks like a budgerigar (虎皮). Later prompts must say Quaker / monk only: no cheek spots, no tiger nape bars, no yellow cere.

16. **When to keep Turbo, and when to drop it.** Operator judgment from the monk-parakeet session. Not a change to D-15 / D-02 product defaults.

    **FL2VA (text-to-video, or a first-frame still).** Turbo quality is acceptable. Prefer the **8-step** FL2V Turbo LoRA over 4 steps: motion and shot-to-shot transitions are smoother. That is already the shipped FL2VA default.

    **Ref2VA (identity stills as Omni Reference).** Turn Turbo **off** and use `workflows/h3-ref2va-quality-15s08-20step-1344.json` (20 steps, 1344×768). Turbo Ref2VA is the fast path; it is a weak identity path even at 8 steps.

    **Species prior can survive Turbo-off.** Even with no Turbo LoRA, monk parakeets (Quakers) in the reference stills can still render as a more generic pet parakeet — in these clips, a **budgerigar-like** bird (cheek spots, barred nape). That is an operator observation, not a training-set audit. A working hypothesis is that the video VAE / DiT prior is dominated by common budgerigars and under-represents monk parakeets. Prompt wording can push back; it does not guarantee a lock.
