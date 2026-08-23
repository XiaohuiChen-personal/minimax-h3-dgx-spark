# H3 on DGX Spark

H3 is not an autoregressive video LLM. It is a **33.1B single-stream diffusion transformer** that denoises video and stereo audio in one packed sequence, conditioned by a frozen **Qwen3-VL-32B**. Output is 24 fps video plus 32 kHz stereo audio.

The public briefing has the full argument and measurements: https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/

## Pipeline

1. **Condition** — Qwen3-VL-32B reads the text prompt once (LM head unused; H3 takes the unnormalized hidden state after layer 50). On the FL2VA node, optional first/last-frame **images** are also tokenized into that prompt.
2. **Encode** — the video VAE (16× spatial, 4× temporal) encodes those same keyframe images into frozen cond latents, and later decodes the generated video. The audio VAE maps 32 kHz stereo ↔ 40 Hz latents. The VAE does not *create* keyframes.
3. **Pack** — text tokens, optional keyframe latents, video noise, and audio noise become one multimodal token sequence with RoPE. Ref2VA reference blocks (`<Picture N>` / `<Video N>`) are a different partition and are not the first product.
4. **Denoise** — 50 DiT blocks rewrite video and audio latents under two flow-matching schedules (`shift` 12/3 without Turbo, 6/3 with Turbo). The released weights are CFG-distilled: no `guidance_scale`, no negative prompt.
5. **Decode** — the two VAEs emit pixels and stereo audio.

There is no KV cache and no continuous batch. Cost scales with **steps × pixels × frames**. That is why canvas size and duration are first-class deploy knobs, not afterthoughts.

## Constraints this box imposes

- **121.7 GiB** usable unified memory. One bf16 DiT (61.7 GiB) plus the bf16 conditioner (62.1 GiB) does not fit. Quantization is required for capacity, not only for speed.
- Compute capability **12.1** (GB10), aarch64. NVIDIA VSR / `nvidia-vfx` is unavailable. Custom CUDA wheels are expensive; prefer stock ComfyUI nodes where possible.
- Frame counts snap to `17n+5` at 24 fps. Legal lengths: 4.46 / 5.17 / 8.00 / 10.13 / 15.08 s.
- Both spatial dimensions must be multiples of 32. Native 1920×1080 is invalid (`1080 / 32 = 33.75`). `H3-Regenerate-2K` was not open-sourced, so 1080p means generate smaller and upscale.
- Video and audio use **different flow clocks**. ComfyUI must be newer than 2026-08-06 (`ModelSamplingAV`, commit `bdcb886a`). Older “Turbo destroys audio” reports are not usable evidence.

## Implication for the later container

The image has to ship a *pipeline* (conditioner, DiT, two VAEs, sampler, upscaler, workflow), not a single engine binary. ComfyUI is the first assembly surface because those pieces are already nodes. vLLM-Omni can sit behind that later if a stable HTTP contract matters more than LoRA and kernel experiments.
