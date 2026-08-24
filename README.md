# MiniMax H3 on DGX Spark

A DGX Spark (GB10) project for running [MiniMax H3](https://huggingface.co/MiniMaxAI/MiniMax-H3) — a 33B joint video-and-audio model — through **ComfyUI**, then packaging that stack so other Spark users can run the same recipe.

**Product:** SSH into a Spark, ask Cursor or Claude to run a locked workflow, get an mp4. One GPU job at a time. The Docker image exists so the next Spark gets the same server.

This repository does **not** host model weights.

**Disclaimer.** MiniMax H3 is under the MiniMax H3 Community License. **Excluded territories** (the European Union, the United Kingdom, the Republic of Korea, and the United States) must request authorization at [platform.minimax.io/h3-license](https://platform.minimax.io/h3-license) and wait for MiniMax’s approval before download or generate. Users **outside** those territories do not use that application path for this. This repository does not grant the license. The image does not check a license env flag (D-13).

## Current status

| Phase | Role | State |
|---|---|---|
| Research | Understand H3, measure this GB10, pick an operating point | Published |
| Design | End-to-end contract an agent can implement | Filled in |
| Implement | Workflows, scripts, Dockerfile | Shipped (`h3-spark:local`, locked graphs) |

**Locked operating point:** generate at `960×544` for **8.00 s** (192 frames), then 2× SPAN to `1920×1088` and crop to 1080p. **Default generate is Ref2VA** (4 steps, D-15). First smoke: **5.17 s**. Optional long: **15.08 s / 362** (never 15.00 / 15.04). Text-only / no identity images uses the FL2VA pair (8 steps).

Site: **https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/**

If you will **implement**, read [`design/`](design/) in this order: architecture → decisions → optimizations → operator → container.

If you want the **measurements**, read the [research briefing](https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/briefing.html).

## Who this is for

- This machine, now that the image and locked graphs exist.
- Other DGX Spark users who want the same path without re-deriving quantization, canvas, step count, and ARM64 traps.

## Deploy on a DGX Spark

The runtime is **Docker**, not a host venv. The image is [`deploy/Dockerfile`](deploy/Dockerfile); Compose is [`deploy/compose.yaml`](deploy/compose.yaml). Pins and build traps: [`deploy/README.md`](deploy/README.md).

This is **linux/arm64 / GB10 only**. Do not build or pull an x86_64 image. Weights stay on the host (`~/h3-weights`). They are never in git and never baked into a Docker layer. If you are in an excluded territory, get MiniMax approval at [platform.minimax.io/h3-license](https://platform.minimax.io/h3-license) **before** `download-weights.sh`.

```bash
git clone https://github.com/XiaohuiChen-personal/minimax-h3-dgx-spark.git
cd minimax-h3-dgx-spark

# Host trees (D-14). download-weights.sh creates the weight subfolders.
mkdir -p "$HOME/h3-output" "$HOME/h3-data"
# Needs the `hf` CLI (huggingface_hub). Do not use huggingface-cli.
./scripts/download-weights.sh "$HOME/h3-weights" --task all
./scripts/check-weights.sh "$HOME/h3-weights" --task all

# From the repository root — compose build.context is `..`
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml up -d
curl -fsS http://127.0.0.1:8188/system_stats

# Default generate: Ref2VA 8.00 s / 192 frames. Leave ComfyUI up; do not restart per video.
# Repeat --ref-image 1–9 times. Identity stills are not first_frame.
./scripts/submit-prompt.sh workflows/h3-ref2va-default-8s.json \
  --prompt "<Picture 1> is the front of the subject. A quiet scene. Stereo room tone. No speech." \
  --seed 42 \
  --name default-8s \
  --ref-image "$HOME/h3-data/blue-front.jpg"
```

SaveVideo writes `$HOME/h3-output/<name>_00001_.mp4`. Do not set `H3_LICENSE_ACK`. If a bind mount is empty, put absolute `H3_WEIGHTS` / `H3_OUTPUT` / `H3_DATA` in `deploy/.env` (paths only; no tokens).

First `compose build` compiles SageAttention 2.2 and torchaudio from source. The image should be about **20 GiB**. If it is ~50 GiB, weights were copied into a layer — that is a bug. The NGC base is `nvcr.io/nvidia/pytorch:25.12-py3`; sign in to NGC if the pull is denied.

## Repository layout

```text
docs/         GitHub Pages: hub, briefing, design pages.
design/       Source of truth (markdown).
deploy/       Dockerfile, compose.yaml, start pins.
workflows/    Five locked ComfyUI graphs (FL2VA pair + Ref2VA 5.17 / 8.00 / 15.08).
scripts/      Download, check-weights, submit/poll, smoke-test, entrypoint.
```

Weights, outputs, and caches stay on the machine. They are gitignored.

Agent rules (single copy for Cursor, Claude Code, and Codex): [`AGENTS.md`](AGENTS.md). `CLAUDE.md` and `.cursor/rules/agents.mdc` only point at that file.

## How an implementing agent should work

```text
design/*.md  ──already locked──►  docs/design/*.html
        │
        └──already shipped──►  workflows/ + scripts/ + deploy/
```

1. Do **not** invent a different model, canvas, or serving stack.
2. Use the five locked graphs and the scripts in [`scripts/README.md`](scripts/README.md). Default generate is `workflows/h3-ref2va-default-8s.json`. ~15 s uses `workflows/h3-ref2va-long-15s08.json` (**15.08 s / 362**). Text-only / no identity images uses the FL2VA pair. Do not add a sixth graph.

| User ask | File | Length |
|---|---|---|
| Default / “about 8 seconds” | `workflows/h3-ref2va-default-8s.json` | **8.00 s / 192** |
| Fast smoke / “about 5 seconds” | `workflows/h3-ref2va-smoke-5s17.json` | **5.17 s / 124** |
| “15 seconds” / “15.04 s” / “about 15 seconds” | `workflows/h3-ref2va-long-15s08.json` | **15.08 s / 362** |
| Text-only / no identity images, about 8 seconds | `workflows/h3-fl2va-default-8s.json` | **8.00 s / 192** |
| Text-only fast smoke | `workflows/h3-fl2va-smoke-5s17.json` | **5.17 s / 124** |

3. Build and start from [`deploy/README.md`](deploy/README.md): `docker compose -f deploy/compose.yaml up -d` from the **repository root**. Do not `cd deploy` and run a bare `docker compose up`.
4. On the Spark: download weights into `~/h3-weights` **subfolders** (`download-weights.sh --task all`), then start once (`H3_TASK=ref2va`). Leave ComfyUI up.
5. If ComfyUI is already up on 8188: default generate is Ref2VA 8.00 s with `--ref-image` (variable 1–9). SaveVideo writes `~/h3-output/<name>_00001_.mp4`, not `<name>.mp4`. Do **not** claim a live Ref2VA mp4 exists yet.

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
| D-15 | Ref2VA is the default generate task; FL2VA stays selectable; `--ref-image` is 1–9 | Adopted for implementation |

## License note

**Excluded territories only.** The Community License names the European Union, the United Kingdom, the Republic of Korea, and the United States as excluded territories, and it also restricts outputs. If you are in one of those territories, request authorization at [platform.minimax.io/h3-license](https://platform.minimax.io/h3-license) and wait for approval before you download weights or generate. If you are **not** in an excluded territory, you do not use that application path. This operator (United States) requested and received approval at that link. The Docker image still does not require `H3_LICENSE_ACK` to start (D-13) — the disclaimer is documentation, not a start lock.
