# Standing decisions

Decisions are numbered so later design notes, workflows, and the Docker image can cite them. Status means:

- **Adopted** — implement unless new evidence reverses it.
- **Provisional** — implement to unblock work; verify on this box before treating it as product default.
- **Superseded** — kept so the wrong reasoning stays visible.

Evidence and measurements are in the [research briefing](https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/).

## D-01 · ComfyUI first

**Status:** adopted

Start with ComfyUI on this Spark. vLLM-Omni is the second path if a production HTTP endpoint becomes the priority.

ComfyUI is the smaller download (~40 GiB selected weights vs ~105 GiB resident on vLLM-Omni), supports Turbo LoRA and the optimization ladder, and leaves headroom to experiment. vLLM-Omni has a vendor `dgx_spark_gb10: verified` profile and an OpenAI-shaped API, but little headroom, no LoRA in the recipe, and a known wedge bug.

**Correction:** FL2VA on one Spark *does* serve text-to-video. `--task-type fl2va` handles `t2va` and keyframe-conditioned `fl2va`. Ref2VA needs the other DiT and a restart.

The first product still uses ComfyUI’s HTTP API (`POST /prompt`) from an SSH’d agent. That is D-08, not a switch to vLLM-Omni.

**Reverses if** multi-user or internet serving matters more than learning and iterating on kernels, LoRAs, and graphs. Then vLLM-Omni, or ComfyUI behind a queue shim.

## D-02 · FP8 DiT, INT8 text encoder

**Status:** provisional

| Component | Checkpoint | Why |
|---|---|---|
| DiT | `minimax_h3_fl2va_pruned_fp8_scaled` | FP8 measured 2.07× BF16 on this GB10; the denoising loop is the hot path |
| Text encoder | `qwen3vl_32b_minimax_h3_int8_convrot` | Runs once; keep quality over NVFP4 |
| Video VAE | `minimax_h3_video_vae_fp16` | Decode quality |
| Audio VAE | `minimax_h3_audio_vae_fp32` | Decode quality |
| Turbo LoRA | BF16 8-step ComfyUI variant | Dialogue default is 8 steps (D-06) |

Launch flags intended for the host and later image: `--fast fp8_matrix_mult --disable-pinned-memory`.

**Reverses if** ComfyUI's H3 path does not hit native `_scaled_mm`. Test: same seed with and without `--fast fp8_matrix_mult`. If step time does not drop substantially, switch the DiT to `fl2va_pruned_bf16`.

Pruned-vs-unpruned quality is still unmeasured.

## D-03 · Native 1312×736

**Status:** superseded by D-05

This optimized the upscale factor. Native high-res sampling is slower than generating small and upscaling, and ~1 MP plus few steps is a reported audio-corruption zone.

## D-04 · SPAN upscaler

**Status:** adopted

SPAN over 362 frames to 1080p: **49.2 s** vs Real-ESRGAN **316.0 s**. It is a PSNR regression network (less temporal shimmer than a GAN) and ships through stock ComfyUI `spandrel` — no custom aarch64 wheel.

Rejected: Real-ESRGAN, NVIDIA VSR (no ARM plan as of 2026-04-01), SeedVR2. Upgrade path if flicker is visible: FlashVSR.

## D-05 · Generate at 960×544, 2× SPAN to 1080p

**Status:** provisional

Same author, same seed, 20 steps, ~5 s: native 1344×768 = **637 s**; 960×540 + 2× = **349.9 s** and a larger frame. `960×544` is the multiple-of-32 neighbor that scales exactly 2.00× to 1920×1088 (crop 8 rows to 1080).

**Reverses if** 2× SPAN is visibly soft. Then generate at 1216×672 (~40% more sampling time), not native 720p.

## D-06 · Eight steps when there is dialogue

**Status:** provisional

Audio is generated in the same loop as video. 4-step Turbo is usable for silent drafts; 8 steps is the cleaner dialogue default. Require ComfyUI newer than 2026-08-06 so video and audio use separate flow clocks.

Duration alone has not been isolated as the cause of unusable audio. See D-07.

## D-07 · Default length 8.00 s

**Status:** adopted

| Use | Length | Frames |
|---|---|---|
| First smoke test | 5.17 s | 124 |
| Production default | 8.00 s | 192 |
| Longer stories | stitch 8.00 s shots | — |

15.08 s is inside the trained range but ~55% slower than 8 s and where most community “unusable audio” reports cluster (Turbo, seed changes, old sampler). Official 8.00 s and 10.13 s samples have valid 32 kHz stereo. Community 5.17 s vs 10.13 s pairs at 1280×768 kept ~−14 dB RMS with no NaNs, clipping, or long silences.

**Reverses if** a same-seed, same-step, same-resolution A/B on this box shows 8.00 s audio clearly worse than 5.17 s.

## D-08 · SSH + agent against a long-lived ComfyUI

**Status:** adopted — this is the product end goal

After deploy, the operator SSHs into the Spark and asks Cursor or Claude to generate. The agent patches a locked workflow and `POST`s it to ComfyUI on port 8188. ComfyUI stays up; weights stay resident. **One GPU job at a time is accepted** for this local box. A second request queues.

The browser UI is optional. vLLM-Omni / a public HTTP API is not the first product.

Full process and limits: [`operator.md`](operator.md).

**Reverses if** the product becomes a multi-user service. Then revisit D-01 (vLLM-Omni or a queue shim). The generation pipeline inside one job does not change.

## Still open (do not pretend these are settled)

- Whether ComfyUI H3 actually uses `_scaled_mm` on this path.
- Pruned vs unpruned visual and audio quality.
- SageAttention 2.2.0 now imports and runs on this GB10 (S=25120, cos 1.000 vs SDPA, 1.62×). Still untested inside a full H3 ComfyUI graph.
- Container base image, weight-mount layout, and ComfyUI version pin — [`container.md`](container.md).
- Whether the default image includes a Turbo LoRA or only the 8-step recipe's LoRA files.
- Whether anyone else gets a ComfyUI UI only, or also a small HTTP shim.
