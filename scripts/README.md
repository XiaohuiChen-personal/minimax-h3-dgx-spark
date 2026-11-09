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
| `submit-prompt.py` / `submit-prompt.sh` | Patch free fields, `POST /prompt`, poll `/history/<id>`, print `OUTPUT <local-path>`. Prompt from `--prompt` or `--prompt-file` (structured multi-line prompts; `../design/prompting.md`). Fails before upload if a `<Picture N>` has no attached still. `--ref-image` is optional, repeatable, **variable 1–9** (`POST /upload/image`). 10+ fail-close. `--first-frame` / `--last-frame` upload and link into a `LoadImage` titled `first_frame` / `last_frame` (keyframe graphs only). Server: `--base-url`, else `$H3_COMFY_URL`, else `http://127.0.0.1:8188`. If the server is not loopback (for example `http://spark-2a60:8188` over Tailscale), or the mp4 is not already under `--output-root`, it downloads the mp4 with `GET /view` and also prints `REMOTE_OUTPUT <host>:~/h3-output/…`. `--timeout` (default 3600 s) includes queue time. |
| `smoke-test.sh` | Live: submit the Ref2VA 5.17 s graph (`--prompt` or `--prompt-file`; forwards `--ref-image`, `--base-url`, `--timeout`). `--offline-mp4`: audio check only (no workflow file, no Docker). Needs `ffprobe` on the machine that runs it. |
| `entrypoint.sh` | `check-weights.sh /opt/ComfyUI/models --task "${H3_TASK:-ref2va}"`, then ComfyUI. No UNET preload. No `H3_LICENSE_ACK`. |

Rules:

- Callable on the Spark host, from the container, and (submit / smoke only) from a remote machine on the tailnet. Submit uses only the Python standard library.
- Do not embed tokens or license keys. Do not gate on `H3_LICENSE_ACK`.
- Do not start or restart ComfyUI from submit/smoke.
- `submit-prompt.sh` is what Cursor or Claude should call.
- Hugging Face: `hf download Comfy-Org/MiniMax-H3 diffusion_models/….safetensors --local-dir "$DIR"`. This Spark has `hf` (1.4.1) and no `huggingface-cli`. Do not pass `--local-dir-use-symlinks` (removed). Do not `--include "*.safetensors"` (whole 471 G repo).
- Downloader `--task` leftover from Task 2: always document and prefer `--task`. Default pull is `--task all`. Start check is `--task "${H3_TASK:-ref2va}"` (shared + Ref2VA). `H3_TASK=fl2va` flips the start gate; it does not change the downloader default.
- `--ref-image`, `--first-frame`, and `--last-frame` files are uploaded; the graph stores the uploaded name, never a path (the native H3 keyframe inputs are IMAGE sockets, so a `/data/…` string could never work). Identity stills (including 3-view sheets) are `--ref-image`, **not** `first_frame`. Leftover `LoadImage` titles stay unlinked `example.png`.
- Print output paths under `~/h3-output` (local), not `/opt/ComfyUI/output/…`.
- `/history` outputs are `images` / `gifs` / `videos` lists of `{filename, subfolder, type}`, not `outputs["9"]["filename"]` as a string list.

Plans: executed FL2VA path [`../docs/superpowers/plans/2026-08-23-h3-comfyui-implement.md`](../docs/superpowers/plans/2026-08-23-h3-comfyui-implement.md); current default-task path [`../docs/superpowers/plans/2026-08-23-h3-ref2va-default.md`](../docs/superpowers/plans/2026-08-23-h3-ref2va-default.md).
