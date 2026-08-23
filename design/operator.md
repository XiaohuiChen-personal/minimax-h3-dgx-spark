# Operator model — product end goal

**Status:** adopted (D-08)

After deploy, a person SSHs into this DGX Spark (or another Spark running the same image) and asks Cursor or Claude to generate a clip. The agent does not build a new graph and does not start a new model process. It fills a **predefined ComfyUI workflow** and submits it to a **long-lived** ComfyUI server.

This is local, single-user inference. **One GPU job at a time is the accepted limit.**

The container and host install exist so that path is repeatable. They are not implemented yet.

## What the product is

```text
SSH / Cursor remote
        │
        ▼
   agent patches workflows/*.json
        │
        ▼
   POST http://127.0.0.1:8188/prompt
        │
        ▼
   ComfyUI (already running, weights resident)
        │
        ▼
   output/<name>.mp4
```

- ComfyUI listens on **8188**. The browser UI is optional (SSH `-L 8188:127.0.0.1:8188`). Agents use the HTTP API.
- Workflow DAGs and locked knobs live in [`../workflows/`](../workflows/). Scripts that submit and poll live in [`../scripts/`](../scripts/).
- Weights stay on a host or volume mount. They are never in git and never baked into the image.

This is not vLLM chat. There is no per-token loop and no new engine per request.

## Operator steps

1. **Leave ComfyUI running.** Start it once (host service or container). Reloading ~40 GiB of weights is the expensive part. Do not restart per video.
2. **SSH into the Spark** and open Cursor or Claude on that machine.
3. **Ask for a generate.** Example: “Use the default 8 s FL2VA workflow. Prompt: … Seed: 42.”
4. **The agent only changes free fields** — prompt, seed, output name, optional first/last-frame **image files** — then `POST /prompt`.
5. **It polls `/history/<prompt_id>`** until the job finishes (minutes, not seconds) and returns the mp4 path under `output/`.

A second `POST /prompt` while one job is running **queues**. That is fine.

## What one generation does

The JSON is assembly. The denoising loop is inside one sampler node.

**Once per job (outside the loop)**

1. Load DiT, Qwen3-VL-32B, VAEs, Turbo LoRA, SPAN — skipped if already resident.
2. Condition: Qwen3-VL encodes the text prompt (LM head unused). If first/last-frame images are attached, the same `MiniMaxH3ImageToVideo` node also feeds those pixels into Qwen3-VL **and** VAE-encodes them as frozen keyframe latents.
3. Allocate empty video + audio latents at `960×544` and a legal frame count.

**Inside the loop (8 steps with Turbo)**

4. Pack text, optional keyframe latents, video noise, and audio noise into one sequence.
5. The 33B DiT denoises both streams on two flow clocks. SageAttention, Sol-Attn, and FirstBlockCache run here if the workflow enabled them.

**After the loop**

6. Decode: video VAE → frames, audio VAE → 32 kHz stereo.
7. SPAN 2× to `1920×1088`, crop to 1080p.
8. Mux `output/<name>.mp4`.

## Fixed vs free

| Locked in the workflow | Agent may change |
|---|---|
| D-02 checkpoints | Text prompt |
| 960×544, 8 steps, SPAN 2× | Seed |
| Legal length: 5.17 s smoke or 8.00 s default | Output filename |
| Sampler, shifts, Sage 2.2, Sol-Attn `triton_ref`, FBC `H3 Safe` | Optional first/last-frame image files |

If the user asks for “10 seconds,” snap to **10.13 s** (243 frames) or refuse. Do not invent 10.00 s. Do not let the agent invent a new DAG for a normal generate.

## Keyframes (optional, same FL2VA graph)

Default is text-only. Pictures are an extra on the same workflow, not a second product and not a separate VAE job.

The agent **attaches image files** to `first_frame` / `last_frame`. The locked node does the rest. Do not “generate keyframes with the VAE” first — the VAE only encodes and decodes.

| What the agent does | What the node does | Result |
|---|---|---|
| Wire `first_frame` / `last_frame` image files | Resize, then `clip.tokenize(prompt, images=…)` | Qwen3-VL sees the pictures as prompt vision tokens (semantics) |
| Same files, same node | `vae.encode` → `minimax_keyframes` cond rows | Pixel lock: frame 1 / last frame *is* that image |
| Write `<Picture 1>` in the prompt only | Nothing useful on this graph | Empty theater. Those tags belong to Ref2VA / the hosted rewriter |

Attaching pictures to the prompt **does not replace** the VAE path. Prompt-only images are semantic. VAE keyframe latents are what make the opening or closing frame match. ComfyUI’s FL2VA node already does both when the image inputs are wired.

Do not switch to `MiniMaxH3ReferenceToVideo` or the Ref2VA DiT for a normal generate. That is a different partition and needs a restart.

## Limits (accepted)

| Limit | Rule |
|---|---|
| One GPU job at a time | Local box; a second request waits in ComfyUI’s queue |
| Warm start | Do not start or restart ComfyUI per video |
| Wall-clock | A warm 8.00 s default is minutes. Agents must poll or background-wait; they must not assume a single chat turn covers the job |
| No multi-user serving | This product is SSH-local, not an internet API. vLLM-Omni remains a later option (D-01) |
| License | Confirm the H3 Community License before any generate. Excluded territories include the US, EU, UK, and South Korea; the restriction covers outputs |

## What the agent must not do

- Download weights or embed tokens in the graph
- Enable EasyCache, SageAttention 3, `--use-sage-attention` as a blind flag, Sol-Attn `flex_attention`, Turbo-SLA on top of Sol-Attn, or `--lowvram`
- Change canvas, steps, or length except to another legal pair (5.17 / 8.00 / 10.13 / 15.08 s)
- Treat `<Picture N>` prompt tags as a substitute for wiring first/last-frame image inputs
- Run a separate VAE encode/decode (or another image model) just to “make keyframes”
- Switch the graph to Ref2VA for a normal first/last-frame generate

## Not built yet

- ComfyUI host install and container
- `workflows/h3-fl2va-smoke-5s17.json` and `workflows/h3-fl2va-default-8s.json`
- `scripts/` submit + poll helper the agent is supposed to call

Until those exist, this document is the contract, not a runnable path.
