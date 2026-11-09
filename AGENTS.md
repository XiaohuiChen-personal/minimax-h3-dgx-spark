# Agent rules — MiniMax H3 on DGX Spark

This file is the **only** copy of the project rules.

| Tool | How it loads these rules |
|---|---|
| Codex | Reads `AGENTS.md` |
| Cursor | Reads `AGENTS.md`, plus `.cursor/rules/agents.mdc` which points here |
| Claude Code | Reads `CLAUDE.md`, which imports this file with `@AGENTS.md` |

Do not fork a second rule set in `CLAUDE.md`, Cursor rules, or chat memory. Edit **this** file.

Product facts live in `design/*.md`. The executed FL2VA implement path is `docs/superpowers/plans/2026-08-23-h3-comfyui-implement.md`. The current default-task plan is `docs/superpowers/plans/2026-08-23-h3-ref2va-default.md` (D-15). Where the active plan is more specific (CLI, mounts, lock tests, close-out), **the plan wins**. Exception: default graphs are a **reference**, not a closed set — copy / modify / create is allowed even when an older plan says “do not invent a DAG” or “do not add a sixth graph.”

## What this repo is

Ask an agent to generate, get an mp4. The agent runs on the DGX Spark itself (over SSH) or on another machine on the same Tailscale tailnet (for example the operator's MacBook). Either way, ComfyUI on the Spark stays up on **8188**. The agent `POST`s an API-format graph to `/prompt`, then polls `/history/<id>`. One GPU job at a time; a second request queues. Do not start a second ComfyUI or a different serving process (no vLLM-Omni as the first path).

The files in `workflows/` are **reference graphs**, not a closed set. Five Turbo defaults (FL2VA pair + Ref2VA 5.17 / 8.00 / 15.08), the FL2VA keyframe graph `workflows/h3-fl2va-keyframes-8s.json`, plus optional Ref2VA quality `workflows/h3-ref2va-quality-15s08-20step-1344.json`. Use one as-is, copy and modify it, or write a new API-format graph when the use case needs different length, canvas, steps, LoRA on/off, or nodes. Do not overwrite a shipped JSON unless the operator asked to change that default. One-off graphs go in a new file.

Public repo: `XiaohuiChen-personal/minimax-h3-dgx-spark`. Pages: https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/

**Status:** ComfyUI image (`h3-spark:local`) and the reference graphs exist (FL2VA pair + FL2VA keyframes + Ref2VA 5.17 / 8.00 / 15.08 Turbo, plus optional Ref2VA quality 15.08 / 20-step / 1344×768). Generate via `scripts/submit-prompt.sh` and poll `/history/<id>`. Default generate is Ref2VA 8.00 s. Live Ref2VA smokes exist on this Spark: `$HOME/h3-output/smoke-ref2va-5s17_00001_.mp4` (5.17 s / 124) and `$HOME/h3-output/smoke-ref2va-15s08_00001_.mp4` (15.08 s / 362). Do not commit the mp4s. SaveVideo adds `_00001_`. Never print `/opt/ComfyUI/output`.

If the user only asked to **make a video**, follow **Generate a video** below (it covers running on the Spark and running remote). Do not re-run the implementation plan.

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
| D-06 | **8 steps** for speech. 4 steps only for silent seed-hunt. ComfyUI newer than `bdcb886a` (`ModelSamplingAV`). Shifts **12 / 3** for the shipped 544p Turbo LoRAs and for no-Turbo (corrected 2026-11-09; 6 / 3 is for 768p LoRAs only). |
| D-07 | Default **8.00 s / 192 frames**. First smoke **5.17 s / 124**. Legal: 4.46 / 5.17 / 8.00 / 10.13 / 15.08 s. Snap “10 s” to **10.13 s** or refuse. Never invent 10.00 s. |
| D-08 | Long-lived ComfyUI. Agent does not restart it per video. |
| D-09 | NGC PyTorch CUDA 13 `linux/arm64` base. Pin the tag at implement time. |
| D-10 | Weights on the host (`~/h3-weights`). Never in git. Never in a Docker layer. Never downloaded at `docker build`. |
| D-11 | Pin ComfyUI SHA after `bdcb886a`. Record it. Do not float on `master`. |
| D-12 | SageAttention **2.2.0** + Sol-Attn **`triton_ref`** + FirstBlockCache **`H3 Safe`** + SPAN. |
| D-13 | Do **not** gate start on `H3_LICENSE_ACK`. Operator accepts Community License risk. Start if weight files exist. |
| D-14 | `deploy/compose.yaml`, image `h3-spark:local`, `~/h3-output`, `~/h3-data`, port 8188. |
| D-15 | Default task is **Ref2VA**. Default generate = `workflows/h3-ref2va-default-8s.json` (8.00 s / 192, **4 steps**, Ref2V Turbo LoRA). Default long = `workflows/h3-ref2va-long-15s08.json` (**15.08 s / 362**). Snap “15 s” / “15.04 s” to 15.08. Never invent 15.00 / 15.04. FL2VA stays selectable. `--ref-image` is variable **1–9** (nine titles `ref_image_0`…`ref_image_8`). 10+ fail-close. 0 refs → FL2VA. These defaults are a starting point; a generate may use a modified or new graph. |

H3 is a 33.1B single-stream DiT that jointly denoises 24 fps video + 32 kHz stereo, conditioned by frozen Qwen3-VL-32B. CFG-distilled. Frames snap to `17n+5`. Dimensions multiples of 32. `H3-Regenerate-2K` is not open-sourced. bf16 DiT + conditioner do not fit.

## Never enable

EasyCache · SageAttention **3** · blind `--use-sage-attention` · Sol-Attn `flex_attention` · Turbo-SLA **plus** Sol-Attn · `--lowvram` / `--novram`.

If Sage or Sol-Attn fail to import, the server may start, but smoke tests must say so. Do not hide the fallback.

## Generate a video (on the Spark, or remote over Tailscale)

ComfyUI on the Spark (port **8188**) is the only generate server, wherever the agent runs. Start from a default graph, or copy / edit / create an API-format graph for this use case. Still `POST /prompt` and poll `/history/<id>`. Do not open a second ComfyUI or a different serving process.

Longer product card: `design/operator.md`. Prompt format: `design/prompting.md` (read it before writing any prompt).

### 0. Where are you running?

```bash
uname -sm; nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null
```

| Result | You are | ComfyUI URL | Files you pass to submit |
|---|---|---|---|
| `Linux aarch64` **and** `NVIDIA GB10` | **On the Spark** | `http://127.0.0.1:8188` (script default) | Paths on the Spark (`~/h3-data/…`) |
| Anything else (for example `Darwin arm64` on a MacBook) | **Remote** | `http://<spark>:8188` over Tailscale | Paths on **this** machine |

When remote:

- This operator's Spark is the Tailscale node **`spark-2a60`** (`ssh spark-2a60` works; its clone is `~/Projects/minimax-h3-dgx-spark`). Another operator: use your Spark's name from `tailscale status`.
- `export H3_COMFY_URL=http://spark-2a60:8188`, then run `./scripts/submit-prompt.sh` from **this** machine's clone. It needs only `python3` (stdlib). It uploads local `--ref-image` / `--first-frame` / `--last-frame` files over HTTP — do **not** `scp` them first. The graph travels in the POST, so the Spark's clone does not have to match.
- Never run H3, Docker, the image, or GPU torch on the remote machine. Never `docker compose` on the laptop.
- `ssh spark-2a60 …` is for read-only checks (`docker ps`, `docker logs`, `ls ~/h3-output`) and for starting ComfyUI **only when the user asked**.

### 1. Confirm the server

```bash
curl -fsS http://127.0.0.1:8188/system_stats      # on the Spark
curl -fsS "$H3_COMFY_URL/system_stats"            # remote
```

Remote and it fails: `ssh spark-2a60 'curl -fsS http://127.0.0.1:8188/system_stats'` tells “ComfyUI is down” apart from “Tailscale cannot reach 8188.” If only the tailnet path fails, tunnel with `ssh -fN -L 8188:127.0.0.1:8188 spark-2a60` and set `H3_COMFY_URL=http://127.0.0.1:8188`. Submit still downloads the mp4, because it is not under the local output root.

If ComfyUI is down: tell the user. Do **not** `docker compose up`, restart, or kill the container unless they explicitly asked you to start it. If they did ask: `cd ~/Projects/minimax-h3-dgx-spark && docker compose -f deploy/compose.yaml up -d` on the Spark (remote: wrap it in `ssh spark-2a60 '…'`). Then poll `/system_stats` until it answers. The first start maps the weights and takes minutes.

One GPU job at a time. A second submit **queues**. That is fine. Do not start a second ComfyUI.

### 2. Pick or make a workflow

The files below are **defaults for reference**. Use one unchanged when it already fits. Copy and modify it, or write a new API-format JSON, when the use case needs something else (10.13 s, different canvas or step count). Do not treat the list as a closed set. Do not overwrite a shipped file unless the operator asked to change that default.

| User ask | Start from | Length |
|---|---|---|
| Default / “about 8 seconds” | `workflows/h3-ref2va-default-8s.json` | **8.00 s / 192** |
| Fast smoke / “about 5 seconds” | `workflows/h3-ref2va-smoke-5s17.json` | **5.17 s / 124** |
| “15 seconds” / “15.04 s” / “about 15 seconds” | `workflows/h3-ref2va-long-15s08.json` | **15.08 s / 362** |
| Quality / no Turbo / 20-step 15 s | `workflows/h3-ref2va-quality-15s08-20step-1344.json` | **15.08 s / 362** |
| Text-only / no identity images, about 8 seconds | `workflows/h3-fl2va-default-8s.json` | **8.00 s / 192** |
| Text-only fast smoke | `workflows/h3-fl2va-smoke-5s17.json` | **5.17 s / 124** |
| Start from a still (I2VA), first + last frame (FL2VA), or end on a still (L2VA) | `workflows/h3-fl2va-keyframes-8s.json` | **8.00 s / 192** |

Snap “15 s” / “15.04 s” to **15.08 s / 362**. Never invent **15.00** or **15.04**. If they say “10 seconds,” snap to **10.13 s / 243** — copy a default graph and set `length` 243, or ask them to accept 8.00 s. Never invent **10.00 s**.

### 3. Write the prompt (structured — see `design/prompting.md`)

H3 was trained on rewritten, structured prompts. MiniMax calls that rewrite step “critical to the quality of the final output.” **You are that rewrite step.** Turn the user's request into the structure below. Do not submit a one-line prompt, and do not ask the user to write the structure.

- **FL2VA graphs** (`MiniMaxH3ImageToVideo`): `integrated_multimodal_description: [Shot 1] …`, then `overall_soundscape: …`, then `non_diegetic_music: …`. Keyframe tasks put the official alignment line first (I2VA: `For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.`).
- **Ref2VA graphs** (`MiniMaxH3ReferenceToVideo`): six sections — `subject_definitions`, `summary` (starts `[reference generation]`), `retention_analysis`, `detailed_description` (350–500 words, style sentence then `[Shot 1] …`), `overall_soundscape`, `non_diegetic_music`. Identity stills are cited inside `<Subject N>` definitions.
- Fill the clip's real duration. Later shots start `[Shot N] At MM:SS.mmm, the camera cuts to …`.
- Speech: `… (S1) says: <d>[English] exact words.</d>`. These are dedicated tokenizer tokens; plain quotes do not use them. No `<d>` block means no intended speech. Write both sound fields (or `N/A` on purpose).
- Write the prompt to a scratch file and pass `--prompt-file`. Multi-line prompts break in shell quoting.

### 4. Inputs you may set

H3 is **CFG-distilled**. There is **one** text field (`prompt`). There is **no** negative prompt and **no** `guidance_scale`. Do not add a second text box, a `negative_prompt` node, or CFG. State the wanted look positively inside the one prompt.

| CLI | Graph field | Required | What to put |
|---|---|---|---|
| `--prompt-file` / `--prompt` | `prompt` (also patches `text` if present) | one of them | The structured prompt from step 3. Prefer `--prompt-file`. On Ref2VA, `<Picture N>` is 1-based in `--ref-image` order. On keyframe graphs, `<Picture 1>` is the first attached keyframe (first frame, else last frame). On text-only FL2VA, no `<Picture N>`. **Submit fails before upload if a `<Picture N>` has no image behind it.** Ref2VA is the 4-step LoRA — weak for speech. For dialogue use FL2VA (8 steps) or the no-Turbo quality graph. |
| `--seed` | `noise_seed` / `seed` | yes | Integer. Reuse the user’s seed; otherwise pick one and tell them. |
| `--name` | `filename_prefix` | yes | Short token, no `/`. Example: `two-birds`. |
| `--ref-image` | `LoadImage` titles `ref_image_0`…`ref_image_8`, then nested `ref_images` | no | Optional, **repeatable**, local files. Uploaded via `POST /upload/image` (not a path in the graph). **Variable 1–9.** This product ships nine `LoadImage` titles. Do **not** say “six only.” Do not claim unbounded N (node max 9; 10+ fail-close). Leftover `LoadImage`s stay unlinked `example.png` and are not in the SaveVideo DAG. **0 refs → submit FL2VA**, not 0-ref Ref2VA. Identity stills (including 3-view sheets) are Ref2VA `--ref-image`, **not** `first_frame`. |
| `--first-frame` / `--last-frame` | `LoadImage` titled `first_frame` / `last_frame`, linked into `MiniMaxH3ImageToVideo` | no | Local stills, uploaded like refs. Only graphs that carry those titled `LoadImage`s accept them (`h3-fl2va-keyframes-8s.json`). Default T2V graphs and all Ref2VA graphs **fail-close**. A keyframe is a real frame of the shot, not an identity sheet. |
| `--timeout` | — | no | Seconds to wait, including queue time (default 3600). Raise it for the ~45 min quality graph or when a job is queued ahead. |

Default-graph knobs (change them on a copy when the use case needs it): Ref2VA uses the D-15 DiT + 4-step Ref2V LoRA; FL2VA uses the D-02 DiT + 8-step FL2V LoRA. Shared Turbo defaults: **960×544** (the 544p LoRAs' training size), Euler+simple, shifts **12 / 3** (what both 544p LoRAs were distilled at — 6 / 3 belongs to the 768p LoRAs we do not ship), Sage 2.2, Sol-Attn `triton_ref`, FBC `H3 Safe`, SPAN 2× → crop 1920×1080, 24 fps + 32 kHz stereo. Ref2VA **4 steps**. FL2VA **8 steps**. Do not strap the FL2V LoRA onto Ref2VA. Operator note (`measurements/turbo-vs-base.md` §16): Turbo is fine on FL2VA (prefer **8 steps** for smoother motion); for Ref2VA identity, prefer Turbo **off** via `workflows/h3-ref2va-quality-15s08-20step-1344.json` (no SPAN, no FBC, no EasyCache; ~45 min on this box). Turning Turbo off does not by itself lock monk parakeets (Quakers) — they can still drift toward a budgerigar-like prior. Name the true traits in every prompt section (`design/prompting.md`).

### 5. Command

From the **repository root** of the clone on the machine you are on. Do not `cd` into `deploy/`.

Default generate (Ref2VA 8.00 s). Repeat `--ref-image` once per still (1–9), in `<Picture N>` order:

```bash
# Write the six-section prompt (design/prompting.md) to a scratch file first.
./scripts/submit-prompt.sh workflows/h3-ref2va-default-8s.json \
  --prompt-file "$SCRATCH/two-birds.txt" \
  --seed 42 \
  --name two-birds \
  --ref-image "$HOME/h3-data/blue-front.jpg" \
  --ref-image "$HOME/h3-data/blue-side.jpg"
```

Text-only / speech (FL2VA 8.00 s, 8 steps):

```bash
./scripts/submit-prompt.sh workflows/h3-fl2va-default-8s.json \
  --prompt-file "$SCRATCH/kitchen-talk.txt" --seed 42 --name kitchen-talk
```

Remote: same commands from the laptop's clone after `export H3_COMFY_URL=http://spark-2a60:8188`. Paths are laptop paths.

The script uploads stills, `POST`s `/prompt`, and polls `/history/<id>` (every 2 s, `--timeout` 3600 s). Jobs take **minutes** (warm FL2VA 5.17 s ~3 min; FL2VA 8.00 s ~5 min; Turbo Ref2VA 15.08 s ~6 min; quality Ref2VA 15.08 s ~45 min on this box). If your shell tool has a time limit shorter than the job, run the command in the background and wait for it to exit. Do not assume one chat turn is enough. Live Ref2VA smokes already exist on this Spark at `$HOME/h3-output/smoke-ref2va-5s17_00001_.mp4` and `$HOME/h3-output/smoke-ref2va-15s08_00001_.mp4`.

### 6. Output

On the Spark, success prints:

```text
OUTPUT /home/<user>/h3-output/<name>_00001_.mp4
```

Remote, success prints both, after downloading the file with `GET /view`:

```text
REMOTE_OUTPUT spark-2a60:~/h3-output/<name>_00001_.mp4
OUTPUT /Users/<user>/h3-output/<name>_00001_.mp4
```

- Tell the user the **host** path(s). SaveVideo adds `_00001_`. There is no unsuffixed `<name>.mp4`.
- Never print `/opt/ComfyUI/output/…`.
- History lists are `images` / `gifs` / `videos` of `{filename, subfolder, type}` (this stack often puts the mp4 under `images`).
- Do not commit or push the mp4.

### Generate contract

On a default graph the usual free fields are **prompt** (structured), **seed**, **filename**, optional **`--ref-image` files** (Ref2VA, variable 1–9), optional **first/last-frame files** (keyframe graphs only). When the use case does not fit a default, copy / modify / create an API-format graph, then call `scripts/submit-prompt.sh` on that file. Still: legal `17n+5` lengths, dimensions multiples of 32, one `prompt` (no CFG / no negative box), ComfyUI already up on the Spark's 8188. Do not start, restart, or kill ComfyUI for a normal generate.

## Downloads and mounts

- Do **not** download H3 weights unless the operator is executing the Ref2VA plan **Task 2** (`download-weights.sh DIR [--task ref2va|fl2va|all]`; default `--task all`).
- `hf download Comfy-Org/MiniMax-H3 <repo-relative-path> --local-dir "$DIR"`.
- Never `huggingface-cli`. Never `--local-dir-use-symlinks`. Never `--include "*.safetensors"` on `Comfy-Org/MiniMax-H3` (that is the **~471 G** snapshot, including Ref2VA).
- Mount **subfolders only**: `diffusion_models`, `text_encoders`, `vae`, `loras`, `upscale_models` → `/opt/ComfyUI/models/<name>`. Do not bind the whole `~/h3-weights` tree over `/opt/ComfyUI/models`.
- Time every artifact pull and append `measurements/download-log.md` (bytes, seconds, MiB/s, **% of 1000 MB/s**). This box is on an **8 Gbps** plan. Cache hits: `n/a` + `cache-hit` — do not divide by zero.
- Official Comfy-Org T2V JSON is a **UI-format template and not D-02** (INT8 DiT, NVFP4 TE, 1344×768, 4 steps, `length` 73). Convert to API format before submit. Do not ship the stock template unchanged as a product default.

## Implementation process

Plans: executed FL2VA path `docs/superpowers/plans/2026-08-23-h3-comfyui-implement.md`; current default-task path `docs/superpowers/plans/2026-08-23-h3-ref2va-default.md`.

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

1. This file — if the user asked to generate a video, read `design/prompting.md`, then stop after **Generate a video**
2. `design/architecture.md` → `decisions.md` → `optimizations.md` → `operator.md` → `container.md`
3. The implementation plan above, if you are building the stack (not a normal generate)

Do not invent a different serving path. ComfyUI on 8188 stays the generate server. Default graphs, canvas, and kernels are the reference starting point — modify or replace the graph when the use case needs it.
