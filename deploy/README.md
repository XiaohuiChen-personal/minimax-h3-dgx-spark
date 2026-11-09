# `deploy/` — Spark runtime and container

Image definition: [`Dockerfile`](Dockerfile). Compose: [`compose.yaml`](compose.yaml). For a new Spark, the numbered clone → weights → `compose` path is in the [root README](../README.md#deploy-on-a-dgx-spark).

Pins recorded at implement time (Task 1 / Task 5 / Task 9). Do not float on `master`.

| Pin | Value |
|---|---|
| `BASE_IMAGE` | `nvcr.io/nvidia/pytorch:25.12-py3` |
| `COMFYUI_SHA` | `b78cec879b9460d5cb25228a83a942fb78d2cd24` |
| `SPAN_FILE` | `upscale_models/2x-spanx2-ch48.pth` |
| Image | `h3-spark:local` |
| Platform | `linux/arm64` |
| SageAttention | **2.2.0** (`eb615cf6cf4d221338033340ee2de1c37fbdba4a`, tag `v2.2.0`) |
| KJNodes | `kijai/ComfyUI-KJNodes` @ `3f20054214fec9f9234fd3841ae6f1e4287948f6` |
| Sol-Attn | `Saganaki22/ComfyUI-sol-attn` @ `930a4d6e432ff8b8ed5e30ff2f72519b92d69bdf` (triton-ref pack) |
| FirstBlockCache | `duckyshell/ComfyUI-MiniMaxH3-FirstBlockCache` @ `725973c3bfd9de6dce249bc93dc5fe27f820df31` (`ApplyMiniMaxH3FirstBlockCache`, `H3 Safe`) |
| ComfyUI patch | [`patches/comfyui-h3-vae-tile-blend.patch`](patches/comfyui-h3-vae-tile-blend.patch) — backport of upstream `fc584aaa` ([Comfy-Org/ComfyUI#16436](https://github.com/Comfy-Org/ComfyUI/pull/16436)); build fails unless [`patches/test_h3_vae_tile_blend.py`](patches/test_h3_vae_tile_blend.py) passes |

Official SageAttention 2.2.0 `SUPPORTED_ARCHS` includes `12.0` and not `12.1`. The image compiles with `TORCH_CUDA_ARCH_LIST=12.0` (sm_120 SASS; the documented GB10 path for unmodified 2.2.0). The `sageattention3_blackwell` tree is deleted before `pip install` so SageAttention 3 is not in the image.

Design of the mounts and start path: [`../design/container.md`](../design/container.md). Compose **subfolder** binds win over any whole-`models` sketch.

Download and image-build timings vs the 8 Gbps (1000 MB/s) ceiling: [`../measurements/download-log.md`](../measurements/download-log.md).

## Host folders (D-14)

| Env | Default |
|---|---|
| `H3_WEIGHTS` | `$HOME/h3-weights` |
| `H3_OUTPUT` | `$HOME/h3-output` |
| `H3_DATA` | `$HOME/h3-data` |

Nested `${H3_WEIGHTS:-${HOME}/h3-weights}` needs Compose v2 and `HOME` in the environment. If a mount is empty, write `deploy/.env` with **absolute** `H3_WEIGHTS` / `H3_OUTPUT` / `H3_DATA` (paths only; do not put tokens in that file).

## Start (no license env flag — D-13)

Weights must already be on the host (`./scripts/check-weights.sh "$HOME/h3-weights" --task all` after a `--task all` pull). Default start (`H3_TASK=ref2va`) requires **shared + Ref2VA**. FL2VA files may stay on disk so that graph is selectable. The entrypoint starts if the start-set files exist. Do not set `H3_LICENSE_ACK`.

```bash
# from the repository root
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml up -d
curl -fsS http://127.0.0.1:8188/system_stats
```

Leave ComfyUI up. Do not restart it for every video.

Compose publishes 8188 on all interfaces, so tailnet peers (for example the operator's MacBook) reach `http://<spark-tailscale-name>:8188` directly. Keep the Spark on a private tailnet; ComfyUI has no auth.

```bash
# default generate: Ref2VA 8.00 s / 192 frames — server must already be up
# --ref-image is optional, repeatable, variable 1–9. 3-view sheets are this flag, not first_frame.
# The prompt is H3's structured six-section format (design/prompting.md), saved to a file.
./scripts/submit-prompt.sh workflows/h3-ref2va-default-8s.json \
  --prompt-file "$HOME/h3-data/prompts/default-8s.txt" \
  --seed 42 \
  --name default-8s \
  --ref-image "$HOME/h3-data/blue-front.jpg"
```

Text-only / no identity images: `workflows/h3-fl2va-default-8s.json`. ~15 s: `workflows/h3-ref2va-long-15s08.json` (**15.08 s / 362**; never 15.00 / 15.04). Quality / no-Turbo 15 s: `workflows/h3-ref2va-quality-15s08-20step-1344.json`. Live Ref2VA smokes exist on this Spark: `$HOME/h3-output/smoke-ref2va-5s17_00001_.mp4` and `$HOME/h3-output/smoke-ref2va-15s08_00001_.mp4`. Do not commit the mp4s.

SaveVideo writes a suffixed host path under `$HOME/h3-output` (for example `default-8s_00001_.mp4`), not `/opt/ComfyUI/output/…`. Do not set `H3_LICENSE_ACK`.

**Disclaimer.** If you are in an excluded territory (EU, UK, Republic of Korea, United States), request MiniMax authorization at https://platform.minimax.io/h3-license and wait for approval before download or generate. If you are not in an excluded territory, you do not use that application path. This file does not grant the license. Documentation only — do not set `H3_LICENSE_ACK` (D-13).

## Build notes

- Dockerfile: `FROM --platform=linux/arm64` the NGC tag above. There is no `PLATFORM` instruction.
- Compose `build.context` is the **repository root** so `COPY workflows` and `COPY scripts` work. Do not change that to `build: .` (that would be `deploy/` only).
- The NGC image Python is GPU torch. Do not replace it with a PyPI `torch` wheel.
- NGC 25.12 does **not** ship `torchaudio`. Prebuilt wheels ABI-mismatch this torch. The image builds **torchaudio 2.9.0 from source** (`--no-deps --no-build-isolation`) so ComfyUI can import `resample` / `MelSpectrogram`. Do not `pip install torchaudio` from PyPI (it will not load, or it will try to replace torch).
- `torch.cuda.is_available()` is a **first-run** check (compose `up` / `/system_stats`), not a `docker build` assert — the build has no GPU.

## ComfyUI patches on top of the pin

The pin stays `b78cec87` (D-11). Upstream fixes that matter for quality are **backported as patch files** in [`patches/`](patches/) and applied in a late Dockerfile layer, so the SageAttention / torchaudio builds stay cached and the rest of the tested stack does not move.

| Patch | Upstream | Why |
|---|---|---|
| `comfyui-h3-vae-tile-blend.patch` | `fc584aaa` / #16436 (merged 2026-09-22) | The pinned H3 VAE `tiled_decode` blended each tile against its neighbours' **raw** edges, leaving a step at every tile intersection (3×4 tiles → 6 crossings per frame at 960×544; SPAN 2× then enlarges them). The patched loop blends against already-blended neighbours. The CPU test checks the real pinned class against a separable overlap-add reference: unpatched max error 2.75, patched 5e-15. |

An image built before this patch still has the seam bug. Rebuild (`docker compose -f deploy/compose.yaml build`) and recreate the container to pick it up — only when the operator asks, because recreating restarts ComfyUI.
