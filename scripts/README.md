# `scripts/` — operators

Empty on purpose. Helpers will land here after the host install path is known.

Expected later jobs:

- Download D-02 checkpoints into a weights directory (not into git, not into the image).
- Check that the weights mount contains every required file before ComfyUI starts.
- Run the 5.17 s smoke-test workflow and fail if audio is missing.

Scripts should be callable both on the host and from the container entrypoint. They must not embed tokens or license keys.
