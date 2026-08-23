# `scripts/` — operators

Empty on purpose. Helpers will land here after the host install path is known.

Expected later jobs (see [`../design/operator.md`](../design/operator.md)):

- Download D-02 checkpoints into a weights directory (not into git, not into the image).
- Check that the weights mount contains every required file before ComfyUI starts.
- Submit a locked workflow (`POST /prompt`) and poll `/history/<prompt_id>`.
- Run the 5.17 s smoke-test workflow and fail if audio is missing.

The submit/poll script is what Cursor or Claude should call. It must not start a new ComfyUI per video.

Scripts should be callable both on the host and from the container entrypoint. They must not embed tokens or license keys.
