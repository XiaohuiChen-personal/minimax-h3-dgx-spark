# `deploy/` — Spark runtime and container

Pins recorded at implement time (Task 1 / Task 5 / Task 9). Do not float on `master`.

| Pin | Value |
|---|---|
| `BASE_IMAGE` | `nvcr.io/nvidia/pytorch:25.12-py3` |
| `COMFYUI_SHA` | `b78cec879b9460d5cb25228a83a942fb78d2cd24` |
| Image | `h3-spark:local` |
| Platform | `linux/arm64` |
| SageAttention | **2.2.0** (`eb615cf6cf4d221338033340ee2de1c37fbdba4a`, tag `v2.2.0`) |
| KJNodes | `kijai/ComfyUI-KJNodes` @ `3f20054214fec9f9234fd3841ae6f1e4287948f6` |
| Sol-Attn | `Saganaki22/ComfyUI-sol-attn` @ `930a4d6e432ff8b8ed5e30ff2f72519b92d69bdf` (triton-ref pack) |
| FirstBlockCache | `duckyshell/ComfyUI-MiniMaxH3-FirstBlockCache` @ `725973c3bfd9de6dce249bc93dc5fe27f820df31` (`ApplyMiniMaxH3FirstBlockCache`, `H3 Safe`) |

Official SageAttention 2.2.0 `SUPPORTED_ARCHS` includes `12.0` and not `12.1`. The image compiles with `TORCH_CUDA_ARCH_LIST=12.0` (sm_120 SASS; the documented GB10 path for unmodified 2.2.0). The `sageattention3_blackwell` tree is deleted before `pip install` so SageAttention 3 is not in the image.

Design of the mounts and start path: [`../design/container.md`](../design/container.md). Compose **subfolder** binds win over any whole-`models` sketch.

## Host folders (D-14)

| Env | Default |
|---|---|
| `H3_WEIGHTS` | `$HOME/h3-weights` |
| `H3_OUTPUT` | `$HOME/h3-output` |
| `H3_DATA` | `$HOME/h3-data` |

Nested `${H3_WEIGHTS:-${HOME}/h3-weights}` needs Compose v2 and `HOME` in the environment. If a mount is empty, write `deploy/.env` with **absolute** `H3_WEIGHTS` / `H3_OUTPUT` / `H3_DATA` (paths only; do not put tokens in that file).

## Start (no license env flag — D-13)

Weights must already be on the host (`./scripts/check-weights.sh "$HOME/h3-weights"`). The entrypoint starts if those files exist. Do not set `H3_LICENSE_ACK`.

```bash
# from the repository root
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml up -d
curl -fsS http://127.0.0.1:8188/system_stats
```

Leave ComfyUI up. Do not restart it for every video.

MiniMax H3 Community License (documentation only, not a start lock): https://platform.minimax.io/h3-license

## Build notes

- Dockerfile: `FROM --platform=linux/arm64` the NGC tag above. There is no `PLATFORM` instruction.
- Compose `build.context` is the **repository root** so `COPY workflows` and `COPY scripts` work. Do not change that to `build: .` (that would be `deploy/` only).
- The NGC image Python is GPU torch. Do not replace it with a PyPI `torch` wheel.
- NGC 25.12 does **not** ship `torchaudio`. Prebuilt wheels ABI-mismatch this torch. The image builds **torchaudio 2.9.0 from source** (`--no-deps --no-build-isolation`) so ComfyUI can import `resample` / `MelSpectrogram`. Do not `pip install torchaudio` from PyPI (it will not load, or it will try to replace torch).
- `torch.cuda.is_available()` is a **first-run** check (compose `up` / `/system_stats`), not a `docker build` assert — the build has no GPU.
