# `deploy/` — Spark runtime and container

Empty on purpose. This folder will hold the Dockerfile, compose file, and host-run notes once:

1. Open items in [`../design/container.md`](../design/container.md) are decided.
2. A host ComfyUI install on this Spark has produced one 5.17 s `960×544` clip with audio (D-05, D-07).

Expected later files (names may change):

```text
deploy/
  Dockerfile
  compose.yaml
  README.md          # this file: how to run on a DGX Spark
```

Until those exist, do not copy third-party ComfyUI images into this tree. The container must follow the design contract, not the other way around.
