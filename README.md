# MiniMax H3 on DGX Spark

A DGX Spark (GB10) project for running [MiniMax H3](https://huggingface.co/MiniMaxAI/MiniMax-H3) — a 33B joint video-and-audio diffusion transformer — through **ComfyUI**, then packaging that stack so other Spark users can run the same recipe.

The long-term deliverable is a documented, Spark-specific **Docker image** plus the ComfyUI workflows and scripts needed to generate 1080p clips with native stereo audio. This repository is being built in phases. Research is published. Design is starting. Host and container deployment are not started.

This repository does **not** host model weights.

## Current status

| Phase | Role | State |
|---|---|---|
| Research | Understand H3, measure this GB10, pick an operating point | Published |
| Design | Lock the deployment contract before writing Docker or workflows | In progress |
| Deploy | Host ComfyUI first, then a reusable container | Not started |

**Research default (provisional):** generate at `960×544` for **8.00 s** (192 frames), 8 steps, then 2× SPAN to `1920×1088` and crop to 1080p. First smoke test: 5.17 s at the same resolution.

Site hub: **https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/**  
Research briefing: **https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/briefing.html**  
Design HTML pages are skeletons until decisions are locked. Working notes are in [`design/`](design/).

## Who this is for

- This machine, while we learn video-and-audio diffusion and turn the briefing into a repeatable install.
- Later, other DGX Spark users who want the same ComfyUI + H3 path without re-deriving quantization, canvas size, step count, and ARM64 pitfalls.

If you only want the findings, read the [briefing](https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/briefing.html). If you want to change a decision, start in [`design/`](design/) markdown; the HTML under `docs/design/` is filled in after a lock.

## Repository layout

```text
docs/         GitHub Pages site: hub, research briefing, design skeletons.
design/       Working markdown for decisions. Promote into docs/design/ when locked.
deploy/       Future Dockerfile, compose file, and Spark runtime notes.
workflows/    Future ComfyUI graph JSON used by the container and by host installs.
scripts/      Future download, smoke-test, and health-check helpers.
```

| Path | What belongs there | What does not |
|---|---|---|
| [`docs/`](docs/) | Public HTML site (briefing + design skeletons) | Dockerfiles, weights, workflow JSON |
| [`design/`](design/) | Working notes until a decision is locked | Runnable install steps |
| [`deploy/`](deploy/) | The image and how to start it on Spark | Research narrative |
| [`workflows/`](workflows/) | Versioned ComfyUI graphs | One-off prompt experiments |
| [`scripts/`](scripts/) | Automation that the image or a host install can call | Model checkpoints |

Weights, ComfyUI outputs, and local caches stay on the machine or in a volume. They are gitignored and will not be baked into the image.

## How the pieces will fit

```text
design/*.md  ──when locked──►  docs/design/*.html
        │
        └──decides──►  workflows/ + scripts/  ──packaged by──►  deploy/
```

1. **Design first.** Open questions that change the image (base, weight mount, ComfyUI pin, Turbo LoRA in or out) are listed in [`design/`](design/). Do not start the Dockerfile until those are explicit.
2. **Host ComfyUI next.** Prove one 5.17 s clip on this Spark with the D-02 weights and D-05 canvas before wrapping anything.
3. **Container last.** The image should reproduce that host recipe: same kernels, same workflow, weights supplied at runtime, UI on port 8188.

vLLM-Omni is a later serving option, not the first deploy path. See [D-01](design/decisions.md#d-01-comfyui-first).

## Standing decisions

Full rationale and reversal conditions live in [`design/decisions.md`](design/decisions.md).

| ID | Decision | Status |
|---|---|---|
| D-01 | ComfyUI first; vLLM-Omni later if an HTTP service is the priority | Adopted |
| D-02 | FP8 DiT (`fl2va_pruned_fp8_scaled`) + INT8 ConvRot text encoder | Provisional |
| D-03 | Native 1312×736 generate | Superseded by D-05 |
| D-04 | SPAN for 2× upscale, not Real-ESRGAN or NVIDIA VSR | Adopted |
| D-05 | Generate at 960×544, then 2× SPAN to 1080p | Provisional |
| D-06 | 8 steps for dialogue; 4 steps only for silent seed-hunting | Provisional |
| D-07 | Default clip length 8.00 s; first smoke test 5.17 s | Adopted |

## License gate

The MiniMax H3 Community License names the United States, EU, UK, and South Korea as excluded territories and also restricts **outputs**. Weights are not access-gated on Hugging Face. Confirm authorization before download or inference: [platform.minimax.io/h3-license](https://platform.minimax.io/h3-license).
