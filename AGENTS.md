# Agent rules — MiniMax H3 on DGX Spark

This file is the **only** copy of the project rules.

| Tool | How it loads these rules |
|---|---|
| Codex | Reads `AGENTS.md` |
| Cursor | Reads `AGENTS.md`, plus `.cursor/rules/agents.mdc` which points here |
| Claude Code | Reads `CLAUDE.md`, which imports this file with `@AGENTS.md` |

Do not fork a second rule set in `CLAUDE.md`, Cursor rules, or chat memory. Edit **this** file.

Product facts live in `design/*.md`. Implementation steps live in `docs/superpowers/plans/2026-08-23-h3-comfyui-implement.md`. Where the plan is more specific (CLI, mounts, lock tests, close-out), **the plan wins**.

## What this repo is

SSH into this DGX Spark, ask an agent to generate, get an mp4. ComfyUI stays up on **8188**. The agent fills a **locked** workflow and `POST /prompt`, then polls `/history/<id>`. One GPU job at a time; a second request queues. Do not start a new process or invent a DAG.

Public repo: `XiaohuiChen-personal/minimax-h3-dgx-spark`. Pages: https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/

**Status:** ComfyUI image (`h3-spark:local`) and locked graphs exist. Generate via `scripts/submit-prompt.sh` and poll `/history/<id>`. Do not invent a new process.

## Hardware and Python traps

- Box: NVIDIA GB10 (`sm_121`), `linux/arm64`, ~121.7 GiB unified memory, CUDA 13, DGX OS.
- System Python ships **CPU-only torch**. Never use `/usr/bin/python3` for GPU work. GPU torch lives in environments such as `~/.vllm` (`torch` 2.10.0+cu130) or the NGC image Python.
- Never build or pull an x86_64 product image. Dockerfile: `FROM --platform=linux/arm64` (there is no `PLATFORM` instruction).
- This Spark has **`hf` 1.4.1**. `huggingface-cli` is not installed.

## Standing decisions (build these)

Full cards: `design/decisions.md`. Do not reopen a locked decision without new measurements on this GB10.

| ID | Build |
|---|---|
| D-01 | ComfyUI first. vLLM-Omni is later, not the first product. |
| D-02 | FP8 DiT `fl2va_pruned_fp8_scaled` + INT8 TE `qwen3vl_32b_int8_convrot` + video VAE fp16 + audio VAE fp32 + Comfy-Org Turbo 8-step BF16 LoRA. Launch: `--fast fp8_matrix_mult --disable-pinned-memory`. |
| D-04 / D-05 | Sample **960×544**. SPAN **2×** → 1920×1088. Crop to 1080p. Not Real-ESRGAN. Not NVIDIA VSR. Not native 1080p (`1080/32` is illegal). |
| D-06 | **8 steps** for speech. 4 steps only for silent seed-hunt. ComfyUI newer than `bdcb886a` (`ModelSamplingAV`). Shifts **6 / 3** with Turbo. |
| D-07 | Default **8.00 s / 192 frames**. First smoke **5.17 s / 124**. Legal: 4.46 / 5.17 / 8.00 / 10.13 / 15.08 s. Snap “10 s” to **10.13 s** or refuse. Never invent 10.00 s. |
| D-08 | Long-lived ComfyUI. Agent does not restart it per video. |
| D-09 | NGC PyTorch CUDA 13 `linux/arm64` base. Pin the tag at implement time. |
| D-10 | Weights on the host (`~/h3-weights`). Never in git. Never in a Docker layer. Never downloaded at `docker build`. |
| D-11 | Pin ComfyUI SHA after `bdcb886a`. Record it. Do not float on `master`. |
| D-12 | SageAttention **2.2.0** + Sol-Attn **`triton_ref`** + FirstBlockCache **`H3 Safe`** + SPAN. |
| D-13 | Do **not** gate start on `H3_LICENSE_ACK`. Operator accepts Community License risk. Start if weight files exist. |
| D-14 | `deploy/compose.yaml`, image `h3-spark:local`, `~/h3-output`, `~/h3-data`, port 8188. |

H3 is a 33.1B single-stream DiT that jointly denoises 24 fps video + 32 kHz stereo, conditioned by frozen Qwen3-VL-32B. CFG-distilled. Frames snap to `17n+5`. Dimensions multiples of 32. `H3-Regenerate-2K` is not open-sourced. bf16 DiT + conditioner do not fit.

## Never enable

EasyCache · SageAttention **3** · blind `--use-sage-attention` · Sol-Attn `flex_attention` · Turbo-SLA **plus** Sol-Attn · `--lowvram` / `--novram`.

If Sage or Sol-Attn fail to import, the server may start, but smoke tests must say so. Do not hide the fallback.

## Generate contract (after the image exists)

Locked in the graph: D-02 files, 960×544, 8 steps, SPAN 2×, Sage 2.2, Sol-Attn `triton_ref`, FBC `H3 Safe`, a legal duration.

Agent may change only: **prompt**, **seed**, **filename**, optional **first/last-frame image files**.

- Call `scripts/submit-prompt.sh` (or `POST /prompt` + poll `/history/<id>`). Jobs take **minutes**.
- Do not start, restart, or kill ComfyUI for a normal generate.
- Keyframes: attach files (`~/h3-data` → `/data` in the graph). `MiniMaxH3ImageToVideo` shows them to Qwen3-VL **and** `vae.encode`s them as frozen `minimax_keyframes`. `<Picture N>` prompt-only is empty theater. Do not switch to Ref2VA for a normal generate.
- Print host paths under `~/h3-output`, not `/opt/ComfyUI/output/…`.
- History outputs are `images` / `gifs` / `videos` lists of `{filename, subfolder, type}`.

## Downloads and mounts

- Do **not** download H3 weights unless the operator is executing **plan Task 6**.
- `hf download Comfy-Org/MiniMax-H3 <repo-relative-path> --local-dir "$DIR"`.
- Never `huggingface-cli`. Never `--local-dir-use-symlinks`. Never `--include "*.safetensors"` on `Comfy-Org/MiniMax-H3` (that is the **~471 G** snapshot, including Ref2VA).
- Mount **subfolders only**: `diffusion_models`, `text_encoders`, `vae`, `loras`, `upscale_models` → `/opt/ComfyUI/models/<name>`. Do not bind the whole `~/h3-weights` tree over `/opt/ComfyUI/models`.
- Time every artifact pull and append `measurements/download-log.md` (bytes, seconds, MiB/s, **% of 1000 MB/s**). This box is on an **8 Gbps** plan. Cache hits: `n/a` + `cache-hit` — do not divide by zero.
- Official Comfy-Org T2V JSON is a **UI-format template and not D-02** (INT8 DiT, NVFP4 TE, 1344×768, 4 steps, `length` 73). Convert to API format and lock this design. Do not ship the template unchanged.

## Implementation process

Plan: `docs/superpowers/plans/2026-08-23-h3-comfyui-implement.md`.

- New Cursor chat, **Multitask mode**, skill `superpowers:subagent-driven-development`. Parent coordinates. Parent does not write `scripts/` or `deploy/` unless a worker is blocked.
- **Cursor workers:** every implementer, spec reviewer, adversarial reviewer, and fixer uses model slug `cursor-grok-4.6-xhigh-fast`. If that slug is missing, **stop**. Do not silently swap models.
- **Claude Code / Codex:** same close-out and same stack. Use the model the operator launched. Do not invent a different product.
- Do not start Task N+1 until Task N close-out (including push) is done, except the plan’s safe parallel table.

**Per-task close-out (mandatory, in order):**

1. Implementer: implement, test, **commit only**.
2. Spec reviewer (read-only).
3. Fixer if Critical/Important.
4. Adversarial reviewer **and fixer** (new subagent): hunt inaccuracies, bugs, silent fallbacks, forbidden flags, tests that pass on stubs, CPU-torch traps, baked weights, license gates, Ref2VA drift. Fix what you can prove. Commit `fix: … after adversarial review of Task N`.
5. **Re-smoke.** Do not `|| true` unit tests. After Task 9: `curl` `/system_stats`. After Task 10: offline mp4 check, and a live re-run if graphs/scripts/image changed. Do not restart ComfyUI for re-smoke.
6. `git push -u origin HEAD`. Never `--force`. Never `--no-verify` unless the operator said so.

## Git and secrets

- Never commit or push `*.safetensors`, `*.pth`, `*.mp4`, `*.whl`, tokens, or `.env`.
- Never update git config. Never force-push `main`. Never skip hooks unless the operator said so.
- Commit only when the operator asks, **except** implementation-plan close-out (that process includes commit + push).
- A one-line license pointer may live in README. It is not a start lock.

## Read order

1. This file
2. `design/architecture.md` → `decisions.md` → `optimizations.md` → `operator.md` → `container.md`
3. The implementation plan above, if you are building

Do not invent a different model, canvas, kernel stack, or serving path.
