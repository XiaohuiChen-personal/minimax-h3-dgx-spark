# Container — build it and start it

This page is the contract for the shipped `deploy/Dockerfile` and `deploy/compose.yaml`, and what a human or agent follows to run the image on a DGX Spark.

The image **exists** (`h3-spark:local`). Pins and start commands live in [`../deploy/README.md`](../deploy/README.md). Do not copy a random ComfyUI image from the internet. The image must match [`decisions.md`](decisions.md).

## What you are building

One **linux/arm64** image that:

1. Starts ComfyUI on port **8188**
2. Already has the H3 nodes, SPAN, Sage 2.2, Sol-Attn `triton_ref`, and FirstBlockCache `H3 Safe`
3. Loads weights from a **host folder** (D-10)
4. Serves the five locked workflows (FL2VA pair + Ref2VA 5.17 / 8.00 / 15.08)
5. Accepts one GPU job at a time (ComfyUI’s own queue)
6. Start-checks **shared + Ref2VA** (`H3_TASK=ref2va` default). FL2VA files may be on disk so that graph stays selectable; they are not required to start unless `H3_TASK=fl2va`

The browser UI on 8188 is optional. The product is `POST /prompt`.

```text
Spark host
  ~/h3-weights/<subdir>  ──ro──►  /opt/ComfyUI/models/<subdir>
  ~/h3-output    ──rw──►  /opt/ComfyUI/output
  ~/h3-data      ──ro──►  /data          (optional identity stills / pictures)

docker compose -f deploy/compose.yaml up -d  →  ComfyUI :8188  →  agent POST /prompt  →  ~/h3-output/*.mp4
```

## What the image contains vs what it must not

| In the image | On the host (mounted) | Never |
|---|---|---|
| NVIDIA GPU PyTorch (CUDA 13, aarch64) | Shared + Ref2VA MiniMax files (FL2VA optional on disk) | MiniMax weights in a layer |
| ComfyUI at a pinned SHA (D-11) | SPAN upscale file | x86_64 build |
| Sol-Attn + H3 FirstBlockCache nodes | Optional identity stills | `--lowvram` |
| SageAttention 2.2.0 wheel | Generated mp4s | SageAttention 3 |
| Locked workflow JSON + scripts | | Silent weight download |

## Host folder layout

Create this tree **before** the first `compose up`. `./scripts/download-weights.sh "$HOME/h3-weights"` defaults to `--task all` so both DiTs land and FL2VA stays selectable. `./scripts/check-weights.sh` verifies a task set (`--task ref2va|fl2va|all`; default `$H3_TASK` or `ref2va`).

**Required to start** (`H3_TASK=ref2va`, the default): shared + Ref2VA.

```text
~/h3-weights/
  text_encoders/
    qwen3vl_32b_minimax_h3_int8_convrot.safetensors      # shared
  vae/
    minimax_h3_video_vae_fp16.safetensors               # shared
    minimax_h3_audio_vae_fp32.safetensors               # shared
  upscale_models/
    2x-spanx2-ch48.pth                                  # shared (SPAN)
  diffusion_models/
    minimax_h3_ref2va_pruned_fp8_scaled.safetensors     # required at default start
  loras/
    minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors
```

**Optional on disk** (needed to *submit* FL2VA, not to start the default container):

```text
  diffusion_models/minimax_h3_fl2va_pruned_fp8_scaled.safetensors
  loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors
```

`H3_TASK=fl2va` flips the start gate to shared + FL2VA. `required-weights.txt` is a compatibility wrapper (shared + default task). Prefer `--task`.

`SPAN_FILE` is `upscale_models/2x-spanx2-ch48.pth` (official 2× SPAN ch48; OpenModelDB). Mount that **subfolder** only.

Source for the MiniMax files: [huggingface.co/Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3).

The entrypoint runs `check-weights.sh /opt/ComfyUI/models --task "${H3_TASK:-ref2va}"`. If any required file is missing, it prints the missing names and exits. It does not start ComfyUI. It does not preload a UNET.

`~/h3-output` and `~/h3-data` may start empty.

## Dockerfile contract (shipped in `deploy/Dockerfile`)

Implemented in `deploy/Dockerfile`. Do not put the file in `docs/`.

1. `FROM` the NGC PyTorch tag pinned in [`../deploy/README.md`](../deploy/README.md) (D-09). Platform `linux/arm64`.
2. Confirm inside the build, or in a documented first-run check, that `python -c "import torch; assert torch.cuda.is_available()"`.
3. Clone ComfyUI at the pinned SHA (D-11) into `/opt/ComfyUI`.
4. Install Python deps with the **image’s** Python, never `/usr/bin/python3` from the Spark host.
5. Install SageAttention **2.2.0** for `sm_121` / `sm_121a`. Do not install 3.x.
6. Install custom nodes:
   - Sol-Attn (ComfyUI node pack that can select kernel `triton_ref`)
   - H3 FirstBlockCache (preset `H3 Safe`)
   - Only other nodes the locked workflows actually call (for example a video-combine node if stock save-video is not enough)
7. Copy `workflows/*.json` and `scripts/*` into the image.
8. `EXPOSE 8188`.
9. `ENTRYPOINT` a small script that:
   - runs the weight-file check (D-10)
   - starts ComfyUI with the launch flags below
   - does **not** require a license env flag (D-13)
10. Labels: `comfyui.git_sha`, `base.image`, `h3.decision_set` (D-01…D-15; the image label is updated when the image is rebuilt).

### Launch flags (required)

```text
python main.py --listen 0.0.0.0 --port 8188 \
  --fast fp8_matrix_mult --disable-pinned-memory
```

### Launch flags (forbidden)

```text
--lowvram
--novram
--use-sage-attention
```

Sage is a **package + workflow path**, not that flag.

## Compose contract

Shipped in `deploy/compose.yaml`. `build.context` is the **repository root** so `COPY workflows` and `COPY scripts` work. Invoke from the repo root — see [`../deploy/README.md`](../deploy/README.md). Do not `cd deploy` and `build: .`.

```yaml
# Real file: deploy/compose.yaml (pins and build.args live there).
services:
  comfyui:
    image: h3-spark:local
    build:
      context: ..
      dockerfile: deploy/Dockerfile
    gpus: all
    ports:
      - "8188:8188"
    volumes:
      - ${H3_WEIGHTS:-${HOME}/h3-weights}/diffusion_models:/opt/ComfyUI/models/diffusion_models:ro
      - ${H3_WEIGHTS:-${HOME}/h3-weights}/text_encoders:/opt/ComfyUI/models/text_encoders:ro
      - ${H3_WEIGHTS:-${HOME}/h3-weights}/vae:/opt/ComfyUI/models/vae:ro
      - ${H3_WEIGHTS:-${HOME}/h3-weights}/loras:/opt/ComfyUI/models/loras:ro
      - ${H3_WEIGHTS:-${HOME}/h3-weights}/upscale_models:/opt/ComfyUI/models/upscale_models:ro
      - ${H3_OUTPUT:-${HOME}/h3-output}:/opt/ComfyUI/output
      - ${H3_DATA:-${HOME}/h3-data}:/data:ro
    restart: unless-stopped
```

Mount **subfolders only**. A whole-tree mount of `~/h3-weights` onto `/opt/ComfyUI/models` hides ComfyUI’s stock extras. Do not mix both schemes. If nested `${HOME}` expansion fails, write `deploy/.env` with absolute `H3_WEIGHTS`.

One service. One GPU. No scale-out.

## Deploy instructions (human or agent, on a Spark)

Do this on the **DGX Spark**, not on a laptop.

### 0. Confirm the box

```bash
uname -m          # must print aarch64
nvidia-smi        # must see the GB10
```

You need Docker with the NVIDIA Container Toolkit, and permission to use the GPU (`--gpus all`).

### 1. Get this repository

```bash
git clone https://github.com/XiaohuiChen-personal/minimax-h3-dgx-spark.git
cd minimax-h3-dgx-spark
```

### 2. Download weights onto the host

```bash
mkdir -p "$HOME/h3-weights" "$HOME/h3-output" "$HOME/h3-data"
./scripts/download-weights.sh "$HOME/h3-weights" --task all
./scripts/check-weights.sh "$HOME/h3-weights" --task all
```

Do not commit the weights. Do not put them in the image.

### 3. Build the image

From the repository root (compose `build.context` is `..`). Exact pins: [`../deploy/README.md`](../deploy/README.md).

```bash
docker compose -f deploy/compose.yaml build
```

Expect a long first build (PyTorch base + ComfyUI + Sage wheel). The image should stay well under the weight set in size. If the build is ~50 GiB, weights were baked in — that is a bug.

### 4. Start the server once

```bash
docker compose -f deploy/compose.yaml up -d
docker compose -f deploy/compose.yaml logs -f
```

Wait until ComfyUI prints that it is listening on 8188. The first start may take several minutes while it maps files. Leave it up. **Do not restart it for every video.**

Health check:

```bash
curl -sS http://127.0.0.1:8188/system_stats
```

A failing start with “missing checkpoint …” means the mount is wrong. Fix the host tree. Do not download from inside the container as a workaround.

### 5. Generate

From another terminal on the same Spark (or SSH with `-L 8188:127.0.0.1:8188`):

```bash
./scripts/submit-prompt.sh workflows/h3-ref2va-default-8s.json \
  --prompt "<Picture 1> is the front of the subject. A quiet scene. Stereo room tone. No speech." \
  --seed 42 \
  --name default-8s \
  --ref-image "$HOME/h3-data/blue-front.jpg"
```

Default generate is the Ref2VA **8.00 s** graph. Fast smoke uses `workflows/h3-ref2va-smoke-5s17.json` (5.17 s). Text-only / no identity images uses the FL2VA pair. The script uploads `--ref-image` files, `POST`s to `http://127.0.0.1:8188/prompt`, and polls `/history/<prompt_id>`. Live Ref2VA smokes exist on this Spark: `$HOME/h3-output/smoke-ref2va-5s17_00001_.mp4` and `$HOME/h3-output/smoke-ref2va-15s08_00001_.mp4`. Do not commit the mp4s. SaveVideo adds `_00001_`. Never print `/opt/ComfyUI/output`.

A second submit while the first is running should **queue**, not crash, and not start a second ComfyUI.

### 6. Stop (only when you mean to free the GPU)

```bash
docker compose -f deploy/compose.yaml down
```

Stopping unloads the ~40 GiB of weights. The next start pays that cost again.

## Raw `docker run` (same contract)

```bash
docker run --gpus all --name h3-comfy \
  -p 8188:8188 \
  -v "$HOME/h3-weights/diffusion_models:/opt/ComfyUI/models/diffusion_models:ro" \
  -v "$HOME/h3-weights/text_encoders:/opt/ComfyUI/models/text_encoders:ro" \
  -v "$HOME/h3-weights/vae:/opt/ComfyUI/models/vae:ro" \
  -v "$HOME/h3-weights/loras:/opt/ComfyUI/models/loras:ro" \
  -v "$HOME/h3-weights/upscale_models:/opt/ComfyUI/models/upscale_models:ro" \
  -v "$HOME/h3-output:/opt/ComfyUI/output" \
  -v "$HOME/h3-data:/data:ro" \
  h3-spark:local
```

Prefer Compose so the mounts stay consistent.

## What is left

The image, compose file, weight scripts (`download-weights.sh --task`, `check-weights.sh --task`), five locked workflows, `submit-prompt.sh` (`--ref-image`), `smoke-test.sh`, and `deploy/README.md` are already in the tree. Do not rewrite them from a pre-implementation sketch.

Live Ref2VA smokes exist on this Spark: `$HOME/h3-output/smoke-ref2va-5s17_00001_.mp4` (5.17 s / 124) and `$HOME/h3-output/smoke-ref2va-15s08_00001_.mp4` (15.08 s / 362). Do not commit the mp4s. SaveVideo adds `_00001_`. Never print `/opt/ComfyUI/output`. Do not invent a different model, canvas, or serving stack.

## What this image is not

- A multi-GPU or x86_64 build
- A 2K regenerate path (`H3-Regenerate-2K` is not open-sourced)
- A public website
- A substitute for reading [`decisions.md`](decisions.md)
