# Standing decisions

An implementing agent treats **Adopted** and **Adopted for implementation** as “build this.” **Provisional** means the same default, but the first real clip on this box can still reverse it. **Superseded** is kept so we do not repeat a mistake.

Evidence: [research briefing](https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/briefing.html).

How to read a card: **what we do**, **why in one sentence**, **what we rejected**, **what would change our mind**.

## D-01 · ComfyUI first

**Status:** adopted

**What we do.** Run MiniMax H3 through **ComfyUI**. The agent talks to ComfyUI’s own HTTP API (`POST /prompt` on port 8188). That *is* the product API (see D-08).

**Why.** Smaller download (~40 GiB of selected files vs ~105 GiB resident on vLLM-Omni), room to try LoRAs and kernels, and the workflow graph is already the recipe we want to lock.

**Rejected.** vLLM-Omni as the first product. It has a vendor Spark profile and a chat-shaped API, but little free memory, no LoRA in the recipe, one DiT at a time, and a known wedge bug. FL2VA on vLLM-Omni *does* serve text-to-video — that old claim was wrong — but it is still not the first path.

**Reverses if** this becomes a multi-user internet service. Then look at vLLM-Omni or a queue in front of ComfyUI.

## D-02 · Smaller number formats for the big models

**Status:** adopted for implementation (verify on the first clip)

**What we do.** Load these exact files from [Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3):

| Role | File under `models/` | About |
|---|---|---|
| Video+audio model (DiT) | `diffusion_models/minimax_h3_fl2va_pruned_fp8_scaled.safetensors` | Fast path; measured ~2× BF16 math on this chip |
| Prompt reader | `text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors` | Runs once; keep quality |
| Video compressor | `vae/minimax_h3_video_vae_fp16.safetensors` | Quality on decode |
| Audio compressor | `vae/minimax_h3_audio_vae_fp32.safetensors` | Quality on decode |
| 8-step helper | `loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` | Must be the Comfy-Org pack (no AdaLN tensors) |

Start ComfyUI with: `--fast fp8_matrix_mult --disable-pinned-memory`.

**Why.** Full-precision DiT plus full-precision Qwen3-VL do not fit. Inside the noisy loop we want speed (FP8). Outside the loop we want prompt quality (INT8, not 4-bit).

**Rejected.** INT8 for the DiT (slower than BF16 on this chip). 4-bit for the prompt reader. The 4-step Turbo LoRA as the dialogue default. larryvrh’s LoRA pack on the pruned DiT (it still has AdaLN pieces the pruned model cannot use).

**Reverses if** the first same-seed test with and without `--fast fp8_matrix_mult` shows almost no speed-up. Then the DiT is not using native FP8 — switch the DiT file to `minimax_h3_fl2va_pruned_bf16.safetensors`.

## D-03 · Native 1312×736

**Status:** superseded by D-05

We once picked the largest frame that upscales neatly. That optimized the wrong thing. Generating big is **slower** than generating small and enlarging, and ~1 megapixel plus few steps is a known bad-audio zone.

## D-04 · SPAN to enlarge

**Status:** adopted

**What we do.** After decode, enlarge with **SPAN** through stock ComfyUI `spandrel` (`ImageUpscaleWithModel`). Not Real-ESRGAN. Not NVIDIA VSR.

**Why.** On this Spark, SPAN was about **6× faster** than Real-ESRGAN on a long 1080p pass, and it is a “make it sharper, don’t invent faces” network, which flickers less on video. It needs no custom ARM wheel. NVIDIA VSR (`nvidia-vfx`) has no ARM plan.

**Rejected.** Real-ESRGAN, NVIDIA VSR, SeedVR2.

**Upgrade later if** the 2× result looks flickery: FlashVSR. Not in the first image.

## D-05 · Generate 960×544, then 2× to 1080p

**Status:** adopted for implementation

**What we do.** Sample at **960×544**. SPAN to **1920×1088**. Crop 8 rows to **1920×1080**. Portrait jobs: **544×960** → **1088×1920**, then crop.

**Why.** 960 and 544 are multiples of 32. 2.00× lands on 1920×1088 with no stretching. A same-author Spark test was faster this way than sampling near 720p. It also keeps the packed token count (~25k at 8 s) far below a SageAttention noise cliff around 160k.

**Rejected.** Native 1312×736 / 1344×768. Native 1920×1080 (illegal). 1024×576 as the default (fine backup, a bit slower).

**Reverses if** 2× SPAN looks soft on this box. Then sample at 1216×672, not native 720p.

## D-06 · Eight steps when there is talking

**Status:** adopted for implementation

**What we do.** **8 steps** for anything with speech or important sound. **4 steps** only for silent seed-hunting. ComfyUI must be newer than 2026-08-06 (`ModelSamplingAV`, commit `bdcb886a`) so video and audio use two clocks.

Ask the sampler for **9** sigma points when the LoRA is “8-step” (the grid includes the final zero). Ask for **5** when using the 4-step LoRA.

Shifts: **6 / 3** with the Turbo LoRA. **12 / 3** without it. Shift follows distillation, not resolution.

**Why.** Audio is made in the same loop as video. Four steps smear dialogue. Older “Turbo killed the audio” reports were often a one-clock sampler bug.

**Rejected.** 4-step as the everyday default. 20-step as the everyday default (too slow for this product).

## D-07 · Default length 8.00 seconds

**Status:** adopted

| Job | Length | Frames (24 fps) |
|---|---|---|
| First smoke test | 5.17 s | 124 |
| Everyday default | 8.00 s | 192 |
| Longer story | several 8.00 s shots, edited later | — |

**Why.** 8.00 s is a legal length, matches MiniMax’s own sample, and is useful. Duration alone was not proven to ruin audio. 15.08 s is allowed but slower, and that is where most “bad audio” stories pile up.

**Rejected.** 15.08 s as the default. Fake 10.00 s (illegal). If someone asks for ten seconds, use **10.13 s** (243 frames) or refuse.

**Reverses if** a same-seed A/B on this box shows 8.00 s audio clearly worse than 5.17 s.

## D-08 · SSH + agent, one job at a time

**Status:** adopted — this is the product

**What we do.** Leave ComfyUI running. SSH in. Ask Cursor or Claude. The agent fills a locked workflow and `POST`s it. A second request **waits in ComfyUI’s queue**. That is accepted.

**Rejected.** A new ComfyUI process per video. A new graph per video. vLLM-Omni or a public website as the first product.

Full story: [`operator.md`](operator.md).

**Reverses if** several people share the box over the internet. Then revisit D-01. The inside of one job does not change.

## D-09 · NVIDIA GPU PyTorch as the image base

**Status:** adopted

**What we do.** `FROM` an official **NVIDIA PyTorch** image for `linux/arm64` with **CUDA 13**, so `torch.cuda.is_available()` is true on GB10. At implement time, take the current NGC tag that satisfies that, and **write the tag into** `deploy/Dockerfile` and the image labels.

**Why.** The Spark’s system Python ships a **CPU-only** torch. Community ComfyUI ARM images often hide that trap. We need GPU torch more than we need a tiny image.

**Rejected.** Starting from system Python. Starting from an x86_64 image. Starting from a CPU torch wheel (`pip install torch` without the `cu130` index).

## D-10 · Weights live on the host, never in the image

**Status:** adopted

**What we do.** The image contains code, nodes, and wheels. It does **not** contain MiniMax H3 weights. A helper script (`scripts/download-weights.sh`, written at implement time) downloads D-02 files plus a SPAN checkpoint into a host folder. The container mounts that folder read-only. If a required file is missing, the entrypoint **exits with a clear list**. It never silently downloads into a layer.

Exact host tree: see [`container.md`](container.md).

**Rejected.** Baking 50 GiB into the image. Downloading weights at `docker build` time. Downloading weights on every `docker run` without asking.

## D-11 · Pin ComfyUI after the two-clock fix

**Status:** adopted

**What we do.** Clone ComfyUI at a commit **newer than** `bdcb886a` (2026-08-06) that already includes MiniMax H3 nodes and `ModelSamplingAV`. Record the SHA in image labels as `comfyui.git_sha`. Do not float on `master` in the published image.

**Why.** Older ComfyUI put video and audio on one clock. Those builds are not evidence and not a base.

## D-12 · First image includes the agreed speed-ups

**Status:** adopted for implementation

**What we do.** The first image and the locked workflows include:

- D-02 files and launch flags
- Turbo 8-step LoRA, 8 steps
- SageAttention **2.2.0** (GB10 wheel). **Never** SageAttention 3. **Never** a blind `--use-sage-attention` flag
- Sol-Attn kernel **`triton_ref` only**
- FirstBlockCache preset **`H3 Safe`**
- SPAN 2×

If Sage or Sol-Attn fail to import, the server may still start, but the smoke test must say so. Do not hide the fallback.

**Rejected.** EasyCache. SageAttention 3. Sol-Attn `flex_attention`. Turbo-SLA on top of Sol-Attn. `--lowvram`. Shipping “stock attention only” as the product default (it can be a debug fallback, not the recipe).

Details: [`optimizations.md`](optimizations.md).

## D-13 · Do not gate start on a license flag

**Status:** adopted

**What we do.** The operator accepts the MiniMax H3 Community License risk. The entrypoint **must start** if the weight files are present. Do **not** require `H3_LICENSE_ACK`, a mounted notice, or an interactive prompt.

README and `deploy/README.md` tell **excluded-territory** users (EU, UK, Republic of Korea, United States) to request approval at [platform.minimax.io/h3-license](https://platform.minimax.io/h3-license) before download or generate. Users outside those territories do not use that path. That disclaimer is documentation, not a start lock.

**Rejected.** Refusing to start until an env flag is set. Making the implementing agent block on a license checklist.

## D-14 · Compose file and host folders

**Status:** adopted

**What we do.**

| Thing | Name |
|---|---|
| Compose file | `deploy/compose.yaml` |
| Image name | `h3-spark:local` (retagged when published) |
| Weights on host | `$HOME/h3-weights` (override with `H3_WEIGHTS`) |
| Outputs on host | `$HOME/h3-output` (override with `H3_OUTPUT`) |
| Optional pictures | `$HOME/h3-data` (override with `H3_DATA`) |
| Publish port | `8188` |

One GPU. `deploy/compose.yaml` is the documented start path. A raw `docker run` example lives next to it for people who do not use Compose.

## D-15 · Ref2VA is the default generate task

**Status:** adopted for implementation

**What we do.** Default task is **Ref2VA**. Files:

| Role | File |
|---|---|
| DiT | `diffusion_models/minimax_h3_ref2va_pruned_fp8_scaled.safetensors` |
| LoRA | `loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors` |
| TE / VAEs / SPAN | unchanged D-02 / D-04 |

Sampler for Ref2VA: Euler + simple, **4 steps** (5 sigma points including the final zero), shifts **6 / 3**, canvas **960×544**, SPAN 2×, Sage / Sol-Attn `triton_ref` / FBC `H3 Safe` unchanged.

Locked Ref2VA lengths (all three graphs share the sampler / canvas / kernels above):

| Role | File | Seconds | Frames (`17n+5`) | `filename_prefix` |
|---|---|---|---|---|
| Fast smoke | `workflows/h3-ref2va-smoke-5s17.json` | 5.17 | 124 | `h3-ref2va-smoke` |
| Default generate | `workflows/h3-ref2va-default-8s.json` | 8.00 | 192 | `h3-ref2va` |
| Long (optional) | `workflows/h3-ref2va-long-15s08.json` | **15.08** | **362** | `h3-ref2va-15s08` |

Snap “15 s” / “15.04 s” to **15.08 s / 362**. Never invent **15.00** or **15.04**. D-07 still rejects 15.08 s as the everyday default — keep the 8.00 s file as generate default.

**Why 4 steps.** Official Ref2V Turbo LoRA is 4-step. There is no Comfy-Org 8-step Ref2V LoRA. Do not strap the FL2V 8-step LoRA onto Ref2VA. D-06’s “8 steps for speech” stays on the FL2VA graphs.

**User selects FL2VA** by passing `workflows/h3-fl2va-default-8s.json` (or the 5.17 s smoke) to `submit-prompt.sh`. To make **start** require FL2VA instead of Ref2VA: `H3_TASK=fl2va` in `deploy/.env` or the compose environment, then recreate the container. Both weight sets should already be on disk because the downloader defaults to `--task all`.

**User selects ~15 s Ref2VA** by passing `workflows/h3-ref2va-long-15s08.json`. Snap “15 s” / “15.04 s” to this file. Do not make it the default generate.

**Reference images (variable 1–9).** All three locked Ref2VA graphs ship nine `LoadImage` titles `ref_image_0`…`ref_image_8`. `--ref-image` is optional and repeatable: host files, uploaded via `POST /upload/image`. Submit wires only the first N nested `ref_images` keys. Leftover `LoadImage` nodes stay unlinked `example.png` and are **not** in the SaveVideo DAG. **10+ fail-close** (node autogrow max 9; submit `MAX_REF_IMAGES = 9`). Do not say “six only.” Do not claim unbounded N. Identity tasks should pass ≥1 `--ref-image`. Zero identity stills → submit an FL2VA graph, not 0-ref Ref2VA. `<Picture N>` is 1-based and matches `--ref-image` order. 3-view sheets are Ref2VA identity, **not** `first_frame`. Task 8/9 smokes used six bird stills (N=6 of 9 slots). Live proofs on this Spark: `$HOME/h3-output/smoke-ref2va-5s17_00001_.mp4` (5.17 s / 124) and `$HOME/h3-output/smoke-ref2va-15s08_00001_.mp4` (15.08 s / 362). Do not commit the mp4s. SaveVideo adds `_00001_`. Never print `/opt/ComfyUI/output`.

**Rejected.** Using `first_frame` for 3-view sheets. Preloading a UNET in the entrypoint. Requiring a license env flag. Shipping the stock R2V template unchanged. Inventing **15.00** or **15.04** graphs. A composite 3-view contact sheet as the primary smoke. Two GPU jobs (one per bird) for the same wiring proof. 15.08 s as the D-07 default. Strapping the FL2V 8-step LoRA onto Ref2VA.

**Reverses if** a same-seed live test on this box shows the 4-step Ref2V LoRA unusable for the operator’s identity jobs. Then keep the locked graphs; do not invent an 8-step Ref2V LoRA by strapping FL2V.

## Still unverified (do not block the first implementation)

These are tests for the first real clip, not open product questions:

- Does ComfyUI’s H3 path actually hit `torch._scaled_mm` with `--fast fp8_matrix_mult`?
- How do pruned vs unpruned pictures and audio look on the same seed?
- Does SageAttention 2.2 stay sane inside a **full** H3 graph (kernel tests already passed)?

If a test fails, follow the reversal line on that decision. Do not invent a fourth stack.
