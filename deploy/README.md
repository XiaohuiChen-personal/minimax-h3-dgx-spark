# `deploy/` — Spark runtime and container

Empty on purpose until implementation. The **design** of the image and the start steps live in [`../design/container.md`](../design/container.md). Read that first.

Expected files:

```text
deploy/
  Dockerfile
  compose.yaml
  README.md          # this file: short pointer + any implement-time tag pins
```

When those exist, this README should state:

- The exact NGC base tag and ComfyUI SHA that were pinned
- `docker compose up -d` (no license env flag — D-13)
- Where weights and outputs live on the host

Until then, do not copy a third-party ComfyUI image into this tree.
