# `scripts/` — helpers the image and the agent call

Empty on purpose. Write these at implement time. They must follow [`../design/container.md`](../design/container.md) and [`../design/operator.md`](../design/operator.md).

| Script | Job |
|---|---|
| `download-weights.sh <dir>` | Download D-02 files (+ SPAN) into the host tree. Never into git. Never into a Docker layer. |
| `check-weights.sh <dir>` | Exit 1 and print missing names if the tree is incomplete. |
| `submit-prompt.sh <workflow.json> --prompt … --seed … --name …` | Patch free fields, `POST /prompt`, poll `/history/<id>`, print the output path. |
| `smoke-test.sh` | Submit the 5.17 s graph. Fail if the mp4 has no stereo audio. |

Rules:

- Callable on the host and from the container.
- Do not embed tokens or license keys.
- Do not start or restart ComfyUI.
- `submit-prompt.sh` is what Cursor or Claude should call.
