# `scripts/` — helpers the image and the agent call

These helpers are already in the tree. Follow [`../design/container.md`](../design/container.md), [`../design/operator.md`](../design/operator.md), and the implementation plan — where the plan is more specific (CLI, mounts, tests), the plan wins.

| Script | Job |
|---|---|
| `required-weights.txt` | Shared relative paths (D-02 + SPAN). Not a download script. |
| `lib/speedlog.sh append …` | One download-log row. Executable script, not sourced-only. |
| `download-weights.sh <dir>` | `hf download` D-02 paths + SPAN into the host tree. Never into git. Never into a Docker layer. |
| `check-weights.sh <dir>` | Exit 1 and print `MISSING <relpath>` if the tree is incomplete. |
| `submit-prompt.py` / `submit-prompt.sh` | Patch free fields, `POST /prompt`, poll `/history/<id>`, print `OUTPUT <host-path>`. |
| `smoke-test.sh` | Live: submit the 5.17 s graph. `--offline-mp4`: audio check only (no workflow file, no Docker). |
| `entrypoint.sh` | Weight check, then ComfyUI. No `H3_LICENSE_ACK`. |

Rules:

- Callable on the host and from the container.
- Do not embed tokens or license keys. Do not gate on `H3_LICENSE_ACK`.
- Do not start or restart ComfyUI from submit/smoke.
- `submit-prompt.sh` is what Cursor or Claude should call.
- Hugging Face: `hf download Comfy-Org/MiniMax-H3 diffusion_models/….safetensors --local-dir "$DIR"`. This Spark has `hf` (1.4.1) and no `huggingface-cli`. Do not pass `--local-dir-use-symlinks` (removed). Do not `--include "*.safetensors"` (whole 471 G repo).
- Host keyframe paths under `~/h3-data` become `/data/…` in the posted graph. Print host output paths under `~/h3-output`, not `/opt/ComfyUI/output/…`.
- `/history` outputs are `images` / `gifs` / `videos` lists of `{filename, subfolder, type}`, not `outputs["9"]["filename"]` as a string list.

Plan: [`../docs/superpowers/plans/2026-08-23-h3-comfyui-implement.md`](../docs/superpowers/plans/2026-08-23-h3-comfyui-implement.md).
