# Operator — how a person and an agent use the server

**Status:** adopted (D-08)

After the image is running, a person SSHs into the Spark and asks Cursor or Claude to make a clip. The agent does **not** build a new graph and does **not** start a new model process. It fills a **predefined** workflow and sends it to a **ComfyUI that is already up**.

This is local, one-user work. **One GPU job at a time is the accepted limit.**

## The product, in one picture

```text
SSH / Cursor
      │
      ▼
agent fills prompt, seed, name, optional pictures
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
3. **Ask for a generate.** Example: “Use the default 8 s workflow. Prompt: … Seed: 42.”
4. **The agent only changes free fields**, then `POST /prompt` (or calls `scripts/submit-prompt.sh`).
5. **It waits by polling** `/history/<prompt_id>` for minutes, then returns the host path under `~/h3-output` (SaveVideo suffix, for example `default-8s_00001_.mp4`).

A second `POST /prompt` while one job is running **queues**. That is fine.

## What one generation does (plain language)

The JSON is a shopping list. The hard work is inside one sampler node.

**Once, before the loop**

1. Load the models if they are not already in memory.
2. Qwen3-VL reads the text. If pictures were attached, the same node also shows them to Qwen **and** compresses them with the video VAE.
3. Make an empty video+audio workspace at 960×544 and a legal frame count.

**Eight times (the Turbo recipe)**

4. Pack text, optional keyframe numbers, video noise, and audio noise into one list.
5. The big model guesses the remaining noise on both picture and sound. SageAttention, Sol-Attn, and FirstBlockCache run here if the workflow turned them on.

**Once, after the loop**

6. Expand numbers back to frames and stereo sound.
7. SPAN 2× to 1920×1088, crop to 1080p.
8. Write `~/h3-output/<name>_00001_.mp4` (SaveVideo suffix; there is no unsuffixed `<name>.mp4`).

## Fixed vs free

| Locked in the workflow | Agent may change |
|---|---|
| D-02 checkpoints | Text prompt |
| 960×544, 8 steps, SPAN 2× | Seed |
| 5.17 s smoke or 8.00 s default | Output filename |
| Sampler, shifts, Sage 2.2, Sol-Attn `triton_ref`, FBC `H3 Safe` | Optional first/last-frame **image files** |

If the user says “10 seconds,” snap to **10.13 s** (243 frames) or refuse. Do not invent 10.00 s. Do not invent a new graph for a normal generate.

## Keyframes (optional, same graph)

Default is text only. Pictures are extra. The VAE does not create them.

The agent **attaches image files** to `first_frame` / `last_frame` (files under `/data` in the container, or `~/h3-data` on the host). The locked node does the rest.

| What the agent does | What the node does | Result |
|---|---|---|
| Wire `first_frame` / `last_frame` files | Resize, then give the pixels to Qwen3-VL with the text | The prompt reader *understands* the photo |
| Same files, same node | `vae.encode` → frozen keyframe rows | Frame 1 / last frame *is* that photo |
| Write `<Picture 1>` in the prompt only | Nothing useful on this graph | Those tags belong to Ref2VA / MiniMax’s hosted rewriter |

Attaching a picture only as “prompt flavor” does **not** lock the first frame. The VAE path is what locks pixels. The official node already does both when the image inputs are wired.

Do not switch to `MiniMaxH3ReferenceToVideo` or the Ref2VA weights for a normal generate. That is another model and needs a restart.

## HTTP contract the submit script must use

ComfyUI is already running.

| Step | Call | Notes |
|---|---|---|
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
- Treat `<Picture N>` prompt tags as a substitute for wiring first/last-frame files
- Run a separate VAE pass or another image model just to “make keyframes”
- Switch the graph to Ref2VA for a normal first/last-frame generate
- Start a second ComfyUI because the first job is “taking too long”

## What is already shipped

- ComfyUI image `h3-spark:local` and `deploy/compose.yaml`
- `workflows/h3-fl2va-smoke-5s17.json` and `workflows/h3-fl2va-default-8s.json`
- `scripts/submit-prompt.sh` (and friends)

Generate only if ComfyUI is already up on 8188. Do not invent a second serving path. Start commands: [`../deploy/README.md`](../deploy/README.md).
