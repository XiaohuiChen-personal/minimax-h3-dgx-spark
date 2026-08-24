# Architecture — how a clip is made

**Audience:** a person or an AI agent who has not trained video models.

MiniMax H3 does **not** write a video the way ChatGPT writes a sentence. It starts from random noise and slowly turns that noise into 24 pictures per second **and** stereo sound, together, in one network.

The output of one job is a single `mp4`: **24 fps video + 32 kHz stereo audio**.

This page is the mental model. Numbers and file names are in [`decisions.md`](decisions.md). How a user asks for a clip is in [`operator.md`](operator.md). How that stack is packaged is in [`container.md`](container.md).

## The one-sentence product

A long-lived ComfyUI server on a DGX Spark holds the models in memory. An agent sends a locked recipe plus a prompt. Minutes later, an mp4 appears in the output folder. One job runs at a time.

```text
you (SSH) → agent → POST /prompt → ComfyUI (already running)
                                      │
                                      ├─ read the prompt once (Ref2VA also reads 1–9 identity stills)
                                      ├─ start from noise
                                      ├─ clean the noise (Ref2VA 4 times / FL2VA 8 times)
                                      ├─ turn latents into pixels + sound
                                      ├─ enlarge to 1080p
                                      └─ write output/<name>.mp4
```

## Two kinds of computer “brain” (why old LLM habits fail)

| Everyday LLM (Qwen, ChatGPT) | H3 (this project) |
|---|---|
| Writes **one word at a time** | Cleans **the whole video at once**, several times |
| Cheap pass, many times | Huge pass, few times (4 on default Ref2VA; 8 on FL2VA) |
| You see words appear | Until the last pass, you only have noisy sludge |
| Remembers past words (KV cache) | Remembers nothing between passes — every pass re-reads everything |
| Cost ≈ number of words | Cost ≈ **steps × picture size × length** |

There is no streaming preview of the finished video. At 50% of the work you do **not** have half a video. You have a full-length clip that still looks like noise.

## The five stages of one job

Think of a film lab, not a chatbot.

### 1. Read the request (condition)

A frozen model called **Qwen3-VL-32B** reads your text once. It does **not** write the video. It turns words into a list of numbers the video model can attend to. Its “chat” head is unused.

On the default **Ref2VA** graph, identity stills (`--ref-image`, variable 1–9) are shown to the same reader. On **FL2VA**, a first-frame or last-frame **picture** would also be shown to Qwen3-VL — the locked FL2VA T2V graphs omit those keys today.

### 2. Shrink pictures and sound into a compact workspace (encode)

Raw pixels and raw audio are too big to chew 8 times. Two small networks called **VAEs** compress them:

- **Video VAE** — shrinks space by 16× and time by 4×. A 960×544, 8.00 s clip becomes a much smaller grid of numbers.
- **Audio VAE** — turns 32 kHz stereo into a 40 Hz latent track.

If you attached first/last-frame pictures, the **same video VAE** also encodes them into frozen “keyframe” numbers. The VAE does not *invent* those pictures. You attach files; it only compresses them.

### 3. Pack everything into one long list (pack)

H3 is **single-stream**. Text numbers, optional keyframe numbers, video noise, and audio noise sit in **one** sequence. Attention reads the whole list. Conditioning is not a side door. It is other rows in the same list.

Only the video-noise rows and the audio-noise rows get rewritten. Text and keyframe rows stay put and are re-read every step.

### 4. Clean the noise (denoise) — this is almost all the runtime

A 33-billion-parameter **DiT** (diffusion transformer) looks at the whole list and guesses “what is still noise.” A sampler subtracts a little of that guess. Default **Ref2VA** does this **4 times** (official Ref2V Turbo LoRA). Selectable **FL2VA** does it **8 times** (official FL2V 8-step LoRA). Do not strap the FL2V LoRA onto Ref2VA.

Video and sound use **two different clocks**. That is why ComfyUI must be new enough to have `ModelSamplingAV`. An old sampler put both streams on one clock and ruined the audio.

There is no negative prompt and no `guidance_scale`. The published weights already baked that in.

### 5. Grow the result back (decode + enlarge)

- Video VAE → frames
- Audio VAE → 32 kHz stereo
- **SPAN** enlarges 960×544 → 1920×1088 (exact 2.00×)
- Crop 8 rows → 1920×1080
- Mux into `output/<name>.mp4`

## Optional pictures (identity stills vs keyframes)

Default generate is **Ref2VA**: identity stills via `--ref-image` (variable **1–9**). Text-only / no identity images uses the FL2VA pair.

| Path | What the agent attaches | What the tags mean |
|---|---|---|
| Ref2VA (default) | Host files with `--ref-image`, uploaded via `POST /upload/image` | 1-based `<Picture N>` in `--ref-image` order. 3-view sheets are **this** path, not `first_frame`. |
| FL2VA (selectable) | Nothing for identity. Locked T2V graphs omit `first_frame` / `last_frame` | Do **not** write `<Picture N>` (empty theater). |

Ref2VA graphs ship nine `LoadImage` titles `ref_image_0`…`ref_image_8`. Submit wires only the first N nested `ref_images` keys. Leftover `LoadImage` nodes stay unlinked `example.png` and are not in the SaveVideo DAG. **10+ fail-close.** Zero identity stills → submit FL2VA, not 0-ref Ref2VA.

Locked Ref2VA lengths (D-15):

| Role | File | Seconds | Frames (`17n+5`) | `filename_prefix` |
|---|---|---|---|---|
| Fast smoke | `workflows/h3-ref2va-smoke-5s17.json` | 5.17 | 124 | `h3-ref2va-smoke` |
| Default generate | `workflows/h3-ref2va-default-8s.json` | 8.00 | 192 | `h3-ref2va` |
| Long (optional) | `workflows/h3-ref2va-long-15s08.json` | **15.08** | **362** | `h3-ref2va-15s08` |

Snap “15 s” / “15.04 s” to **15.08 s / 362**. Never invent **15.00** or **15.04**. 15.08 is not the everyday default.

Live Ref2VA smokes exist on this Spark: `$HOME/h3-output/smoke-ref2va-5s17_00001_.mp4` (5.17 s / 124) and `$HOME/h3-output/smoke-ref2va-15s08_00001_.mp4` (15.08 s / 362). Do not commit the mp4s. SaveVideo adds `_00001_`. Never print `/opt/ComfyUI/output`.

## Hard rules the hardware and the model both enforce

These are not style choices. The container cannot dodge them.

| Rule | What happens if you ignore it |
|---|---|
| Both width and height must be multiples of **32** | Hard error. 1920×1080 is illegal (`1080 / 32 = 33.75`). We generate 960×544 instead. |
| Frame count must be **17n + 5** at 24 fps | Duration snaps. Legal useful lengths: **4.46 / 5.17 / 8.00 / 10.13 / 15.08 s**. “10 seconds” means **10.13 s**, not 10.00. |
| This box has **~121.7 GiB** of shared CPU+GPU memory | Full-precision DiT + full-precision Qwen3-VL do not fit together. We use smaller number formats (D-02). |
| The chip is **GB10**, compute **12.1**, CPU is **ARM64** | NVIDIA’s video-upscale SDK (`nvidia-vfx`) does not exist here. Custom CUDA wheels are painful. Prefer stock ComfyUI nodes. |
| System `python3` on this Spark is **CPU-only torch** | A container or venv that uses that Python will look like it “works” and then run on the CPU. Always use a CUDA 13 GPU torch. |

## What we generate vs what we skip

| We ship | We do not ship first |
|---|---|
| **Ref2VA as the default generate path** (5.17 / 8.00 / **15.08** graphs) | Native 1080p or the closed `H3-Regenerate-2K` path |
| FL2VA as the selectable text-only pair (no identity images) | 0-ref Ref2VA as an identity generate; unbounded `--ref-image` |
| 960×544 → SPAN → 1080p | Invented **15.00** / **15.04** / **10.00** graphs |
| One GPU job, local SSH | Multi-user public API, vLLM-Omni |
| 8.00 s default generate; 5.17 s smoke; 15.08 optional long | 15.08 s as the everyday default |

## Cost, in one line

**Time ≈ steps × megapixels × seconds of video.**

That is why we generate a smaller frame and enlarge it, and why Ref2VA uses 4 steps and FL2VA uses 8 instead of 20. Making the attention math cheaper (Sage, Sol-Attn) and skipping some repeated work (FirstBlockCache) is extra. The big knobs are still size, length, and step count. See [`optimizations.md`](optimizations.md).

## What the container must contain (conceptually)

Not one magic binary. A **pipeline**:

1. Qwen3-VL (read the prompt)
2. Ref2VA DiT by default; FL2VA DiT when that graph is posted (ComfyUI loads the UNET the graph names — no entrypoint preload)
3. Video VAE + audio VAE (compress / expand)
4. Ref2V 4-step Turbo LoRA on Ref2VA; FL2V 8-step Turbo LoRA on FL2VA
5. SPAN (enlarge)
6. Sampler that knows two clocks (`ModelSamplingAV`)
7. Five locked workflow JSON files (FL2VA pair + Ref2VA 5.17 / 8.00 / 15.08)
8. A submit/poll helper (`--ref-image` uploads identity stills)

ComfyUI is the assembly surface because those pieces are already nodes. The Docker image is that assembly, frozen, plus GPU torch that actually sees the GB10.
