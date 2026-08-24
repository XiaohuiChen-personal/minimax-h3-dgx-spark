# Container — build it and start it

This page is what an implementing agent follows to write `deploy/Dockerfile` and `deploy/compose.yaml`, and what a human follows to run the image on a DGX Spark.

The image is **not written yet**. Do not copy a random ComfyUI image from the internet and call it done. The image must match [`decisions.md`](decisions.md).

## What you are building

One **linux/arm64** image that:

1. Starts ComfyUI on port **8188**
2. Already has the H3 nodes, SPAN, Sage 2.2, Sol-Attn `triton_ref`, and FirstBlockCache `H3 Safe`
3. Loads weights from a **host folder** (D-10)
4. Serves the two locked workflows
5. Accepts one GPU job at a time (ComfyUI’s own queue)

The browser UI on 8188 is optional. The product is `POST /prompt`.

```text
Spark host
  ~/h3-weights/<subdir>  ──ro──►  /opt/ComfyUI/models/<subdir>
  ~/h3-output    ──rw──►  /opt/ComfyUI/output
  ~/h3-data      ──ro──►  /data          (optional first/last-frame pictures)

docker compose up  →  ComfyUI :8188  →  agent POST /prompt  →  ~/h3-output/*.mp4
```

## What the image contains vs what it must not

| In the image | On the host (mounted) | Never |
|---|---|---|
| NVIDIA GPU PyTorch (CUDA 13, aarch64) | D-02 MiniMax files (~52 GiB) | MiniMax weights in a layer |
| ComfyUI at a pinned SHA (D-11) | SPAN upscale file | x86_64 build |
| Sol-Attn + H3 FirstBlockCache nodes | Optional keyframe pictures | `--lowvram` |
| SageAttention 2.2.0 wheel | Generated mp4s | SageAttention 3 |
| Locked workflow JSON + scripts | | Silent weight download |

## Host folder layout

Create this tree **before** the first `compose up`. The download script (next implementation step) should create it.

```text
~/h3-weights/
  diffusion_models/
    minimax_h3_fl2va_pruned_fp8_scaled.safetensors
  text_encoders/
    qwen3vl_32b_minimax_h3_int8_convrot.safetensors
  vae/
    minimax_h3_video_vae_fp16.safetensors
    minimax_h3_audio_vae_fp32.safetensors
  loras/
    minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors
  upscale_models/
    2x-spanx2-ch48.pth
```

`SPAN_FILE` is `upscale_models/2x-spanx2-ch48.pth` (official 2× SPAN ch48; OpenModelDB). Mount that **subfolder** only.

Source for the MiniMax files: [huggingface.co/Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3).

The entrypoint checks those **MiniMax** paths. If any file is missing, it prints the missing names and exits. It does not start ComfyUI.

`~/h3-output` and `~/h3-data` may start empty.

## Dockerfile contract (what to write later)

Implement in `deploy/Dockerfile`. Do not put the file in `docs/`.

1. `FROM` the NGC PyTorch tag chosen at implement time (D-09). Platform `linux/arm64`.
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
10. Labels: `comfyui.git_sha`, `base.image`, `h3.decision_set=D-01..D-14`.

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

Implement in `deploy/compose.yaml`:

```yaml
# Shape only — write the real file at implement time.
services:
  comfyui:
    image: h3-spark:local
    build: .
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

After the download script exists:

```bash
mkdir -p "$HOME/h3-weights" "$HOME/h3-output" "$HOME/h3-data"
./scripts/download-weights.sh "$HOME/h3-weights"
./scripts/check-weights.sh "$HOME/h3-weights"
```

Until that script exists, download the D-02 files by hand from Comfy-Org/MiniMax-H3 into the tree above. Do not commit them. Do not put them in the image.

### 3. Build the image

```bash
cd deploy
docker compose build
```

Expect a long first build (PyTorch base + ComfyUI + Sage wheel). The image should stay well under the weight set in size. If the build is ~50 GiB, weights were baked in — that is a bug.

### 4. Start the server once

```bash
docker compose up -d
docker compose logs -f
```

Wait until ComfyUI prints that it is listening on 8188. The first start may take several minutes while it maps files. Leave it up. **Do not restart it for every video.**

Health check (after the helper exists, or with curl):

```bash
curl -sS http://127.0.0.1:8188/system_stats
```

A failing start with “missing checkpoint …” means the mount is wrong. Fix the host tree. Do not download from inside the container as a workaround.

### 5. Generate

From another terminal on the same Spark (or SSH with `-L 8188:127.0.0.1:8188`):

```bash
./scripts/submit-prompt.sh workflows/h3-fl2va-smoke-5s17.json \
  --prompt "A quiet kitchen, morning light, a glass of water on the table." \
  --seed 42 \
  --name smoke-5s17
```

The script `POST`s to `http://127.0.0.1:8188/prompt` and polls `/history/<prompt_id>` until the job finishes. First smoke test must be **5.17 s**. If that mp4 has video **and** stereo audio, then the default 8.00 s workflow is allowed.

A second submit while the first is running should **queue**, not crash, and not start a second ComfyUI.

### 6. Stop (only when you mean to free the GPU)

```bash
cd deploy && docker compose down
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

## What the implementing agent writes next

In this order, in a later session:

1. `scripts/download-weights.sh` — `hf download` into the host tree (not `huggingface-cli`; that binary is not on this Spark). No tokens in the file. Never `--include "*.safetensors"` on Comfy-Org/MiniMax-H3 (that is the 471 G snapshot).
2. `scripts/check-weights.sh` — exit 1 with a file list if anything required is missing.
3. `workflows/h3-fl2va-smoke-5s17.json` and `workflows/h3-fl2va-default-8s.json` — see [`../workflows/README.md`](../workflows/README.md).
4. `scripts/submit-prompt.sh` — patch free fields, `POST /prompt`, poll `/history`.
5. `scripts/smoke-test.sh` — submit the 5.17 s graph; fail if the mp4 has no audio stream.
6. `deploy/Dockerfile` + `deploy/compose.yaml` + a short `deploy/README.md` that points here.

Do not start those files with a different model, canvas, or serving stack.

## What this image is not

- A multi-GPU or x86_64 build
- A 2K regenerate path (`H3-Regenerate-2K` is not open-sourced)
- A public website
- A substitute for reading [`decisions.md`](decisions.md)
