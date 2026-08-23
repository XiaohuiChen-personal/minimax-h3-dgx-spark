# MiniMax H3 on DGX Spark

Research notes for deploying [MiniMax H3](https://huggingface.co/MiniMaxAI/MiniMax-H3) — a 33B joint video-and-audio diffusion transformer — on an NVIDIA DGX Spark (GB10).

This repository does **not** host model weights. It holds the briefing that records architecture, hardware measurements, quantization choices, and the current production default.

## Read the briefing

GitHub Pages (rendered HTML):

**https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/**

Source file: [`docs/index.html`](docs/index.html)

## Current default

Generate at `960×544` for **8.00 seconds** (192 frames), 8 denoising steps, then 2× SPAN to `1920×1088` and crop to 1080p. First smoke test: 5.17 s at the same resolution.

## License gate

The MiniMax H3 Community License names the United States, EU, UK, and South Korea as excluded territories and also restricts outputs. Confirm authorization before downloading or running weights: `platform.minimax.io/h3-license`.
