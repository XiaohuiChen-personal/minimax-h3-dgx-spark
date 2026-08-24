# Design — what to build

These notes are the contract. The shipped workflows, scripts, and Docker image must keep following them **without inventing a new stack**.

Read in this order:

1. [`architecture.md`](architecture.md) — what the machine does, in plain language
2. [`decisions.md`](decisions.md) — the numbered choices (D-01…D-15)
3. [`optimizations.md`](optimizations.md) — what to speed up, and what never to turn on
4. [`operator.md`](operator.md) — how a person and an agent use the running server
5. [`container.md`](container.md) — how to build and start the Docker image

Public HTML (same content, for humans):

- [Architecture](https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/design/architecture.html)
- [Decisions](https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/design/decisions.html)
- [Optimizations](https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/design/optimizations.html)
- [Operator](https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/design/operator.html)
- [Container](https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/design/container.html)

Evidence behind the numbers lives in the [research briefing](https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/briefing.html). Do not reopen a locked decision without new measurements on this GB10.

## What is already decided

The product is: SSH into a DGX Spark, ask Cursor or Claude to generate, get an mp4. One GPU job at a time. ComfyUI stays up. The graph is predefined. **Default generate is Ref2VA 8.00 s** (D-15). FL2VA stays the text-only / no-identity path.

Executed FL2VA implement path:

- [`docs/superpowers/plans/2026-08-23-h3-comfyui-implement.md`](../docs/superpowers/plans/2026-08-23-h3-comfyui-implement.md)

Current default-task plan (D-15):

- [`docs/superpowers/plans/2026-08-23-h3-ref2va-default.md`](../docs/superpowers/plans/2026-08-23-h3-ref2va-default.md)

That plan is the implementation path for Ref2VA as default. Locked graphs are in the tree. Do **not** claim a live Ref2VA mp4 exists yet (Task 8/9). Do not invent a different model, canvas, kernel stack, or serving path.

Start commands and pins: [`../deploy/README.md`](../deploy/README.md). Evidence: [`../measurements/prereq.md`](../measurements/prereq.md), [`../measurements/download-log.md`](../measurements/download-log.md).

Implementation details that override the shape sketches in this folder:

- **Mounts:** bind each weight *subfolder* (`diffusion_models`, `text_encoders`, `vae`, `loras`, `upscale_models`). Do not mount the whole `~/h3-weights` tree over `/opt/ComfyUI/models`.
- **SPAN:** `upscale_models/2x-spanx2-ch48.pth` (`SPAN_FILE`).
- **Downloads:** `hf download Comfy-Org/MiniMax-H3 <repo-relative-path> --local-dir "$DIR"`. `download-weights.sh DIR [--task ref2va|fl2va|all]` (default `--task all`). Not `huggingface-cli`, not `--local-dir-use-symlinks`, not `--include "*.safetensors"` (471 G including Ref2VA).
- **Start set:** shared + Ref2VA (`H3_TASK=ref2va`). FL2VA files are optional on disk.
- **Stock T2V / R2V templates** are UI-format and **not** this product. Convert to API format and lock this design.

Shipped files that must keep following this design:

- `workflows/h3-ref2va-smoke-5s17.json`
- `workflows/h3-ref2va-default-8s.json`
- `workflows/h3-ref2va-long-15s08.json`
- `workflows/h3-fl2va-smoke-5s17.json`
- `workflows/h3-fl2va-default-8s.json`
- `scripts/` download (`--task`), check-weights, submit/poll (`--ref-image`), smoke-test
- `deploy/Dockerfile` and `deploy/compose.yaml`
