# Target container contract

This is the intended shape of the image other DGX Spark users should be able to pull and run. It is a contract, not an implementation. Do not add a Dockerfile until the open items below are decided and a host ComfyUI run has produced one 5.17 s clip on this box.

## Goal

One aarch64 image that reproduces the host recipe:

- ComfyUI new enough to include `ModelSamplingAV` (after 2026-08-06)
- D-02 checkpoints loaded from a **host or volume mount**, not from the image layers
- D-05 / D-07 workflow from [`../workflows/`](../workflows/) (not written yet)
- UI reachable on **8188**
- Optional later: a thin HTTP shim in front of ComfyUI, or a second image for vLLM-Omni

The image exists so a second Spark does not have to rediscover wheels, launch flags, and graph wiring.

## Hard constraints the image must respect

- Platform: `linux/arm64`, GB10, compute capability 12.1, unified memory.
- Do not bake MiniMax H3 weights. They are large, licensed, and machine-local. The container must fail clearly if the mount is missing.
- Do not enable `--lowvram` / CPU offload. On unified memory that copies through a slow path and buys no capacity.
- Do not depend on NVIDIA VSR / `nvidia-vfx`.
- Prefer stock ComfyUI nodes (`spandrel` / SPAN) over custom CUDA extensions. SageAttention is an opt-in acceleration, not a required first image.

## Proposed runtime shape (not implemented)

```text
docker run --gpus all \
  -p 8188:8188 \
  -v /path/to/h3-weights:/models:ro \
  -v /path/to/outputs:/output \
  <image>
```

| Mount | Purpose |
|---|---|
| `/models` | DiT, text encoder, VAEs, optional Turbo LoRA, SPAN weights |
| `/output` | Generated mp4 / audio |
| `/data` (optional) | Reference images for i2va / fl2va / ref2va |

Exact host paths, compose file names, and NGC vs local build are still open.

## Open decisions (block the Dockerfile)

1. **Base image.** NVIDIA Spark / NGC PyTorch with CUDA 13, vs a slimmer ComfyUI community ARM image. Must provide `torch` that actually uses the GPU — system Python on this box is CPU-only and is a known trap.
2. **Weight acquisition.** Documented `huggingface-cli` download into the mount vs a helper in [`../scripts/`](../scripts/). Never a silent download into the image.
3. **ComfyUI pin.** Commit or release newer than `bdcb886a`, recorded here and in the image labels.
4. **Default workflow.** One FL2VA graph at 960×544 / 8.00 s / 8 steps, plus a 5.17 s smoke-test graph. Turbo 4-step is not the default.
5. **Acceleration set.** First image: stock attention. Later tag or build-arg for SageAttention 2.2.0 once it is runtime-tested on this GB10.
6. **Network API.** ComfyUI UI only for the first image. FastAPI shim and vLLM-Omni are separate decisions (see D-01).
7. **License acknowledgement.** The entrypoint should refuse to start unless the operator has confirmed the H3 Community License / excluded-territory status. Mechanism TBD (env flag vs mounted notice).

## What the first image is not

- A multi-GPU or x86_64 build
- A 2K regenerate path (`H3-Regenerate-2K` is not open-sourced)
- A substitute for reading [`decisions.md`](decisions.md)
