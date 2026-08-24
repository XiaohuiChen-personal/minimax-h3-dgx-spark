# Operator — how a person and an agent use the server

**Status:** adopted (D-08)

After the image is running, a person SSHs into the Spark and asks Cursor or Claude to make a clip. The agent does **not** build a new graph and does **not** start a new model process. It fills a **predefined** workflow and sends it to a **ComfyUI that is already up**.

This is local, one-user work. **One GPU job at a time is the accepted limit.**

## The product, in one picture

```text
SSH / Cursor
      │
      ▼
agent fills prompt, seed, name, optional --ref-image stills
      │
      ▼
POST http://127.0.0.1:8188/prompt
      │
      ▼
ComfyUI (weights already in memory)
      │
      ▼
~/h3-output/<name>_00001_.mp4     (24 fps + 32 kHz stereo; SaveVideo suffix)
```

- Port **8188**. The web UI is optional (`ssh -L 8188:127.0.0.1:8188`). Agents use the HTTP API.
- Locked graphs: [`../workflows/`](../workflows/). Submit helper: [`../scripts/`](../scripts/).
- Weights stay on the host. Never in git. Never baked into the image.

This is not a chat model. There is no word-by-word loop.

## Everyday steps

1. **Leave ComfyUI running.** Start it once (`docker compose -f deploy/compose.yaml up -d` from the repo root — see [`container.md`](container.md) and [`../deploy/README.md`](../deploy/README.md)). Reloading the models is the expensive part.
2. **SSH into the Spark** and open Cursor or Claude there.
3. **Ask for a generate.** Default is Ref2VA 8.00 s (`workflows/h3-ref2va-default-8s.json`) plus identity stills. Example: “Use the default 8 s workflow. Prompt: … Seed: 42. These stills: …”
4. **The agent only changes free fields**, uploads `--ref-image` host files via `POST /upload/image` when identity stills were given, then `POST /prompt` (or calls `scripts/submit-prompt.sh`).
5. **It waits by polling** `/history/<prompt_id>` for minutes, then returns the host path under `~/h3-output` (SaveVideo suffix, for example `default-8s_00001_.mp4`).

A second `POST /prompt` while one job is running **queues**. That is fine.

## What one generation does (plain language)

The JSON is a shopping list. The hard work is inside one sampler node.

**Once, before the loop**

1. Load the models if they are not already in memory.
2. Qwen3-VL reads the text. On Ref2VA, identity stills (`--ref-image`, 1–9) are shown to the same reader. On FL2VA, optional first/last-frame files would also go to Qwen **and** the video VAE — the locked T2V graphs omit those keys today.
3. Make an empty video+audio workspace at 960×544 and a legal frame count.

**Four times on Ref2VA (official Ref2V Turbo). Eight times on FL2VA (official FL2V 8-step).**

4. Pack text, optional keyframe numbers, video noise, and audio noise into one list.
5. The big model guesses the remaining noise on both picture and sound. SageAttention, Sol-Attn, and FirstBlockCache run here if the workflow turned them on.

**Once, after the loop**

6. Expand numbers back to frames and stereo sound.
7. SPAN 2× to 1920×1088, crop to 1080p.
8. Write `~/h3-output/<name>_00001_.mp4` (SaveVideo suffix; there is no unsuffixed `<name>.mp4`).

## Fixed vs free

| Locked in the workflow | Agent may change |
|---|---|
| D-15 Ref2VA DiT + 4-step LoRA (or D-02 FL2VA when that graph is chosen) | Text prompt |
| 960×544, SPAN 2×, Euler+simple, shifts 6 / 3 | Seed |
| Ref2VA **4 steps** / FL2VA **8 steps** | Output filename |
| Sampler, Sage 2.2, Sol-Attn `triton_ref`, FBC `H3 Safe` | Optional `--ref-image` host files (Ref2VA, variable 1–9) |
| Length of the chosen locked file | Optional first/last-frame files (rejected on today’s locked FL2VA T2V graphs) |

Locked Ref2VA lengths (D-15):

| Role | File | Seconds | Frames (`17n+5`) | `filename_prefix` |
|---|---|---|---|---|
| Fast smoke | `workflows/h3-ref2va-smoke-5s17.json` | 5.17 | 124 | `h3-ref2va-smoke` |
| Default generate | `workflows/h3-ref2va-default-8s.json` | 8.00 | 192 | `h3-ref2va` |
| Long (optional) | `workflows/h3-ref2va-long-15s08.json` | **15.08** | **362** | `h3-ref2va-15s08` |

Snap “15 s” / “15.04 s” to **15.08 s / 362**. Never invent **15.00** or **15.04**. If the user says “10 seconds,” snap to **10.13 s** (243 frames) or refuse. Do not invent 10.00 s. Do not invent a new graph for a normal generate. Text-only / no identity images uses `workflows/h3-fl2va-default-8s.json` (or the 5.17 s smoke).

## Identity stills (default Ref2VA) vs FL2VA keyframes

Default generate is **Ref2VA**. Identity stills — including 3-view sheets — are `--ref-image` host files, **not** `first_frame`.

The agent uploads each still with `POST /upload/image`, then `submit-prompt.py` sets `LoadImage.image` to the uploaded name and writes a nested `ref_images` dict. Graphs ship nine titles `ref_image_0`…`ref_image_8`. **Variable 1–9.** Leftover `LoadImage` nodes stay unlinked `example.png` and are not in the SaveVideo DAG. **10+ fail-close.** Zero identity stills → submit an FL2VA graph, not 0-ref Ref2VA. Task 8/9 smokes still use six bird stills (N=6 of 9 slots).

| What the agent does | What the node does | Result |
|---|---|---|
| Repeat `--ref-image` on a Ref2VA graph (1–9 host files) | Upload, then nest `ref_images.ref_image_0`… | Identity condition. Prompt uses `<Picture 1>`…`<Picture N>` in upload order |
| Write `<Picture N>` on an FL2VA graph | Nothing useful | Empty theater — do not do this |
| Treat a 3-view sheet as `first_frame` | Fail-close on locked FL2VA T2V graphs | Wrong path. Use Ref2VA `--ref-image` |
| Omit `--ref-image` on Ref2VA | POST without a `ref_images` dict | Node-legal, not a proven identity generate |

To make **start** require FL2VA weights instead of Ref2VA: `H3_TASK=fl2va` in `deploy/.env` or the compose environment, then recreate the container. Selecting FL2VA for a generate is passing the FL2VA JSON to `submit-prompt.sh`. Both weight sets should already be on disk (`download-weights.sh` defaults to `--task all`).

Do **not** claim a live Ref2VA mp4 exists yet (Task 8/9).

## HTTP contract the submit script must use

ComfyUI is already running.

| Step | Call | Notes |
|---|---|---|
| Upload stills | `POST /upload/image` per `--ref-image` | Host files only. Graph stores the uploaded name, not a host path |
| Submit | `POST /prompt` with the workflow JSON | Free fields already patched |
| Remember | JSON field `prompt_id` | |
| Wait | `GET /history/<prompt_id>` every few seconds | Jobs take **minutes**. Do not assume one chat turn is enough. |
| Done | History shows outputs | Return the host path under `~/h3-output` |
| Busy | Another `POST /prompt` | Must queue, not spawn a second server |

Do not start Docker, do not `docker compose restart`, and do not `kill` ComfyUI as part of a normal generate.

## Limits (accepted)

| Limit | Rule |
|---|---|
| One GPU job at a time | Local box; the next request waits in the queue |
| Warm start | Do not start or restart ComfyUI per video |
| Wall-clock | A warm 8.00 s job is minutes |
| No multi-user serving | SSH-local. vLLM-Omni is a later D-01 option |
| License | Excluded-territory users (EU, UK, Republic of Korea, United States) request approval at [platform.minimax.io/h3-license](https://platform.minimax.io/h3-license). Others do not. Do not block a generate on an ack flag (D-13). |

## What the agent must not do

- Download weights or put tokens in the graph
- Enable EasyCache, SageAttention 3, a blind `--use-sage-attention` flag, Sol-Attn `flex_attention`, Turbo-SLA on top of Sol-Attn, or `--lowvram`
- Change canvas, steps, or length except to another legal pair (5.17 / 8.00 / 10.13 / 15.08 s)
- Treat `<Picture N>` prompt tags as a substitute for `--ref-image` uploads, or write them on an FL2VA graph
- Treat a 3-view sheet as `first_frame`
- Run a separate VAE pass or another image model just to “make keyframes”
- Strap the FL2V 8-step LoRA onto a Ref2VA graph, or invent **15.00** / **15.04** lengths
- Start a second ComfyUI because the first job is “taking too long”

## What is already shipped

- ComfyUI image `h3-spark:local` and `deploy/compose.yaml` (`H3_TASK` defaults to `ref2va`)
- Five locked graphs: FL2VA pair + `h3-ref2va-smoke-5s17.json` / `h3-ref2va-default-8s.json` / `h3-ref2va-long-15s08.json`
- `scripts/submit-prompt.sh` (and friends), including `--ref-image`

Locked Ref2VA JSON is in the tree. Do **not** claim a live Ref2VA mp4 exists yet.

Generate only if ComfyUI is already up on 8188. Do not invent a second serving path. Start commands: [`../deploy/README.md`](../deploy/README.md).
