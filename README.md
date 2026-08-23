# MiniMax H3 on DGX Spark

A DGX Spark (GB10) project for running [MiniMax H3](https://huggingface.co/MiniMaxAI/MiniMax-H3) — a 33B joint video-and-audio model — through **ComfyUI**, then packaging that stack so other Spark users can run the same recipe.

**Product:** SSH into a Spark, ask Cursor or Claude to run a locked workflow, get an mp4. One GPU job at a time. The Docker image exists so the next Spark gets the same server.

This repository does **not** host model weights.

## Current status

| Phase | Role | State |
|---|---|---|
| Research | Understand H3, measure this GB10, pick an operating point | Published |
| Design | End-to-end contract an agent can implement | Filled in |
| Implement | Workflows, scripts, Dockerfile | Not started |

**Locked operating point:** generate at `960×544` for **8.00 s** (192 frames), 8 steps, then 2× SPAN to `1920×1088` and crop to 1080p. First smoke test: **5.17 s**.

Site: **https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/**

If you will **implement**, read [`design/`](design/) in this order: architecture → decisions → optimizations → operator → container.

If you want the **measurements**, read the [research briefing](https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/briefing.html).

## Who this is for

- This machine, while we turn the design into a running image.
- Other DGX Spark users who want the same path without re-deriving quantization, canvas, step count, and ARM64 traps.

## Repository layout

```text
docs/         GitHub Pages: hub, briefing, filled design pages.
design/       Source of truth for implementers (markdown).
deploy/       Future Dockerfile and compose.yaml.
workflows/    Future locked ComfyUI graphs.
scripts/      Future download, submit/poll, and smoke-test helpers.
```

Weights, outputs, and caches stay on the machine. They are gitignored.

Agent rules (single copy for Cursor, Claude Code, and Codex): [`AGENTS.md`](AGENTS.md). `CLAUDE.md` and `.cursor/rules/agents.mdc` only point at that file.

## How an implementing agent should work

```text
design/*.md  ──already locked──►  docs/design/*.html
        │
        └──next session──►  workflows/ + scripts/ + deploy/
```

1. Do **not** invent a different model, canvas, or serving stack.
2. Write the two workflows and the scripts named in [`scripts/README.md`](scripts/README.md).
3. Write `deploy/Dockerfile` and `deploy/compose.yaml` from [`design/container.md`](design/container.md).
4. On the Spark: download weights to `~/h3-weights`, then `docker compose up -d`.
5. Smoke-test 5.17 s. Then the 8.00 s default is allowed.

vLLM-Omni is a later option, not the first path ([D-01](design/decisions.md#d-01--comfyui-first)).

## Standing decisions

Full cards: [`design/decisions.md`](design/decisions.md).

| ID | Decision | Status |
|---|---|---|
| D-01 | ComfyUI first; vLLM-Omni later | Adopted |
| D-02 | FP8 DiT + INT8 text encoder, listed files | Adopted for implementation |
| D-03 | Native 1312×736 | Superseded by D-05 |
| D-04 | SPAN for 2× upscale | Adopted |
| D-05 | Generate 960×544, then 2× to 1080p | Adopted for implementation |
| D-06 | 8 steps for dialogue | Adopted for implementation |
| D-07 | Default 8.00 s; smoke 5.17 s | Adopted |
| D-08 | SSH + agent, one GPU job at a time | Adopted |
| D-09 | NVIDIA GPU PyTorch CUDA 13 ARM64 base | Adopted |
| D-10 | Weights on the host, never in the image | Adopted |
| D-11 | Pin ComfyUI after `bdcb886a` | Adopted |
| D-12 | Sage 2.2 + Sol-Attn `triton_ref` + FBC H3 Safe | Adopted for implementation |
| D-13 | Do not gate start on a license flag; operator accepts the risk | Adopted |
| D-14 | Compose file and `~/h3-weights` / `~/h3-output` | Adopted |

## License note

The MiniMax H3 Community License exists and names excluded territories and output restrictions. This operator accepts that risk. The image does not require an acknowledgement flag to start (D-13). Pointer: [platform.minimax.io/h3-license](https://platform.minimax.io/h3-license).
