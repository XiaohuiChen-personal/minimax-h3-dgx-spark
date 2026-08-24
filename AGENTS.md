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

If the user only asked to **make a video**, follow **Generate a video** below. Do not re-run the implementation plan.

If a user is in an **excluded territory** (EU, UK, Republic of Korea, United States), tell them to request MiniMax approval at [platform.minimax.io/h3-license](https://platform.minimax.io/h3-license) before download or generate. Users **outside** those territories do not use that application path. Do **not** add `H3_LICENSE_ACK` or refuse a generate on this box because of a missing env flag (D-13).

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

## Generate a video (SSH + agent)

You are on this Spark, in this repo. ComfyUI should already be up on **8188**. The agent fills a **locked** graph. It does not open a new process, edit the canvas, or invent nodes.

Longer product card: `design/operator.md`.

### 1. Confirm the server

```bash
curl -fsS http://127.0.0.1:8188/system_stats
```

If that fails: tell the user ComfyUI is down. Do **not** `docker compose up`, restart, or kill the container unless they explicitly asked you to start it.

One GPU job at a time. A second submit **queues**. That is fine. Do not start a second ComfyUI.

### 2. Pick a locked workflow

| User ask | File | Length |
|---|---|---|
| Default / “about 8 seconds” | `workflows/h3-fl2va-default-8s.json` | **8.00 s / 192** |
| Fast smoke | `workflows/h3-fl2va-smoke-5s17.json` | **5.17 s / 124** |

Do not add a third graph. If they say “10 seconds,” snap to **10.13 s** or refuse. Never invent **10.00 s**. There is no locked 10.13 s JSON in this repo — refuse or ask them to accept 8.00 s.

### 3. Inputs you may set

H3 is **CFG-distilled**. There is **one** text field (`prompt`). There is **no** negative prompt and **no** `guidance_scale`. Do not add a second text box, a `negative_prompt` node, or CFG. Put “avoid X” in the same sentence if the user cares.

| CLI | Graph field | Required | What to put |
|---|---|---|---|
| `--prompt` | `prompt` (also patches `text` if present) | yes | **One** English (or mixed) string. This is joint **video + stereo audio**. Describe what is on screen **and** what is heard. If they want speech, write that someone is speaking and, when they gave lines, quote the lines. A silent scene (e.g. “quiet kitchen”) yields room tone, not dialogue. |
| `--seed` | `noise_seed` / `seed` | yes | Integer. Reuse the user’s seed; otherwise pick one and tell them. |
| `--name` | `filename_prefix` | yes | Short token, no `/`. Example: `kitchen-talk`. |
| `--first-frame` / `--last-frame` | `first_frame` / `last_frame` | no | **Not usable on the two locked T2V graphs today.** Those JSONs omit the keys so `--first-frame` **fail-closes**. Do not add empty IMAGE keys. Do not write `<Picture N>` in the prompt (empty theater). Do not switch to Ref2VA. If they need image-to-video, say the locked T2V path cannot take stills yet. |

Locked (do not change): D-02 checkpoints, **960×544**, **8 steps**, Euler+simple, shifts **6 / 3**, Sage 2.2, Sol-Attn `triton_ref`, FBC `H3 Safe`, SPAN 2× → crop 1920×1080, 24 fps + 32 kHz stereo.

### 4. Command

From the **repository root**. Do not `cd` into `deploy/`.

```bash
./scripts/submit-prompt.sh workflows/h3-fl2va-default-8s.json \
  --prompt "A person facing the camera and speaking clearly. She says: 'Good morning.' Natural room light. Stereo room tone and intelligible speech." \
  --seed 42 \
  --name kitchen-talk
```

The script `POST`s `/prompt` and polls `/history/<id>` (2 s, timeout 3600 s). Jobs take **minutes** (warm 5.17 s was ~3 min; warm 8.00 s was ~5 min on this box). Wait. Do not assume one chat turn is enough.

### 5. Output

On success the script prints:

```text
OUTPUT /home/<user>/h3-output/<name>_00001_.mp4
```

- Tell the user that **host** path. SaveVideo adds `_00001_`. There is no unsuffixed `<name>.mp4`.
- Never print `/opt/ComfyUI/output/…`.
- History lists are `images` / `gifs` / `videos` of `{filename, subfolder, type}` (this stack often puts the mp4 under `images`).
- Do not commit or push the mp4.

### Generate contract (same rules)

Agent may change only: **prompt**, **seed**, **filename**, optional **first/last-frame files** (rejected on today’s T2V graphs). Call `scripts/submit-prompt.sh`. Do not start, restart, or kill ComfyUI for a normal generate.

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

1. This file — if the user asked to generate a video, stop after **Generate a video**
2. `design/architecture.md` → `decisions.md` → `optimizations.md` → `operator.md` → `container.md`
3. The implementation plan above, if you are building the stack (not a normal generate)

Do not invent a different model, canvas, kernel stack, or serving path.
