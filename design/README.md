# Design — what to build

These notes are the contract. An implementing agent should be able to read them and then write the workflows, scripts, and Docker image **without inventing a new stack**.

Read in this order:

1. [`architecture.md`](architecture.md) — what the machine does, in plain language
2. [`decisions.md`](decisions.md) — the numbered choices (D-01…D-14)
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

The product is: SSH into a DGX Spark, ask Cursor or Claude to generate, get an mp4. One GPU job at a time. ComfyUI stays up. The graph is predefined.

Implementation plan (tasks, tests, download-speed log vs 8 Gbps):

- [`docs/superpowers/plans/2026-08-23-h3-comfyui-implement.md`](../docs/superpowers/plans/2026-08-23-h3-comfyui-implement.md)

That plan is the executed implementation path. Tasks 1–10 are done (5.17 s smoke PASSed). Task 11 is the default **8.00 s** generate plus docs pins (`BASE_IMAGE`, `COMFYUI_SHA`, `SPAN_FILE`, `docker compose -f deploy/compose.yaml up -d`, no `H3_LICENSE_ACK`). Remaining after Task 11’s implementer commit: parent close-out (spec review → adversarial review **and fix** → re-smoke → **`git push`**, never force). Do not invent a different model, canvas, kernel stack, or serving path.

Start commands and pins: [`../deploy/README.md`](../deploy/README.md). Evidence: [`../measurements/prereq.md`](../measurements/prereq.md), [`../measurements/download-log.md`](../measurements/download-log.md).

Implementation details that override the shape sketches in this folder:

- **Mounts:** bind each weight *subfolder* (`diffusion_models`, `text_encoders`, `vae`, `loras`, `upscale_models`). Do not mount the whole `~/h3-weights` tree over `/opt/ComfyUI/models`.
- **SPAN:** `upscale_models/2x-spanx2-ch48.pth` (`SPAN_FILE`).
- **Downloads:** `hf download Comfy-Org/MiniMax-H3 <repo-relative-path> --local-dir "$DIR"`. Not `huggingface-cli`, not `--local-dir-use-symlinks`, not `--include "*.safetensors"` (471 G including Ref2VA).
- **Stock T2V template** is UI-format and **not** D-02 (INT8 DiT, NVFP4 TE, 1344×768, 4 steps, `length` 73, node id 124 is a scheduler). Convert to API format and lock this design.

Shipped files that must keep following this design:

- `workflows/h3-fl2va-smoke-5s17.json`
- `workflows/h3-fl2va-default-8s.json`
- `scripts/` download, check-weights, submit/poll, smoke-test
- `deploy/Dockerfile` and `deploy/compose.yaml`
