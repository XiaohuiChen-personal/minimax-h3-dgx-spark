# `scripts/` — helpers the image and the agent call

These helpers are already in the tree. Follow [`../design/container.md`](../design/container.md), [`../design/operator.md`](../design/operator.md), and the active plan — where the plan is more specific (CLI, mounts, tests), the plan wins.

| Script | Job |
|---|---|
| `required-weights-shared.txt` | TE + VAEs + SPAN. Always included. |
| `required-weights-ref2va.txt` | Ref2VA DiT + 4-step Ref2V LoRA. Default start set. |
| `required-weights-fl2va.txt` | FL2VA DiT + 8-step FL2V LoRA. Optional on disk; required to *submit* FL2VA. |
| `required-weights.txt` | Compatibility wrapper: shared + default task (`H3_TASK` or `ref2va`). Prefer `--task`. |
| `lib/speedlog.sh append …` | One download-log row. Executable script, not sourced-only. |
| `download-weights.sh <dir> [--task ref2va\|fl2va\|all]` | `hf download` the chosen set into the host tree. **Default `--task all`** so both DiTs land and FL2VA stays selectable. Never into git. Never into a Docker layer. |
| `check-weights.sh <dir> [--task ref2va\|fl2va\|all]` | Exit 1 and print `MISSING <relpath>` if the tree is incomplete. Default task is `$H3_TASK` if set, else `ref2va`. |
| `submit-prompt.py` / `submit-prompt.sh` | Patch free fields, `POST /prompt`, poll `/history/<id>`, print `OUTPUT <host-path>`. `--ref-image` is optional, repeatable, **variable 1–9** (host files, `POST /upload/image`). 10+ fail-close. |
| `smoke-test.sh` | Live: submit the Ref2VA 5.17 s graph (forwards `--ref-image`). `--offline-mp4`: audio check only (no workflow file, no Docker). |
| `entrypoint.sh` | `check-weights.sh /opt/ComfyUI/models --task "${H3_TASK:-ref2va}"`, then ComfyUI. No UNET preload. No `H3_LICENSE_ACK`. |

Rules:

- Callable on the host and from the container.
- Do not embed tokens or license keys. Do not gate on `H3_LICENSE_ACK`.
- Do not start or restart ComfyUI from submit/smoke.
- `submit-prompt.sh` is what Cursor or Claude should call.
- Hugging Face: `hf download Comfy-Org/MiniMax-H3 diffusion_models/….safetensors --local-dir "$DIR"`. This Spark has `hf` (1.4.1) and no `huggingface-cli`. Do not pass `--local-dir-use-symlinks` (removed). Do not `--include "*.safetensors"` (whole 471 G repo).
- Downloader `--task` leftover from Task 2: always document and prefer `--task`. Default pull is `--task all`. Start check is `--task "${H3_TASK:-ref2va}"` (shared + Ref2VA). `H3_TASK=fl2va` flips the start gate; it does not change the downloader default.
- `--ref-image` host files are uploaded; the graph stores the uploaded name, not a host path and not `/data/…`. Identity stills (including 3-view sheets) are this flag, **not** `first_frame`. Leftover `LoadImage` titles stay unlinked `example.png`.
- Host keyframe / still paths under `~/h3-data` become `/data/…` only for `--first-frame` / `--last-frame` (rejected on today’s locked FL2VA T2V graphs). Print host output paths under `~/h3-output`, not `/opt/ComfyUI/output/…`.
- `/history` outputs are `images` / `gifs` / `videos` lists of `{filename, subfolder, type}`, not `outputs["9"]["filename"]` as a string list.

Plans: executed FL2VA path [`../docs/superpowers/plans/2026-08-23-h3-comfyui-implement.md`](../docs/superpowers/plans/2026-08-23-h3-comfyui-implement.md); current default-task path [`../docs/superpowers/plans/2026-08-23-h3-ref2va-default.md`](../docs/superpowers/plans/2026-08-23-h3-ref2va-default.md).
