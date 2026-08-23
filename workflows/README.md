# `workflows/` — ComfyUI graphs

Empty on purpose. Versioned workflow JSON will live here once the host pipeline is proven.

Expected later files:

```text
workflows/
  h3-fl2va-smoke-5s17.json     # 960×544, 124 frames, 8 steps
  h3-fl2va-default-8s.json     # 960×544, 192 frames, 8 steps, SPAN 2×
```

These files are what an SSH’d agent submits (see [`../design/operator.md`](../design/operator.md)). Canvas, steps, sampler, and length stay locked. The agent only fills prompt, seed, filename, and optional `first_frame` / `last_frame` image files.

The default graph is `MiniMaxH3ImageToVideo` (text-only, or first/last-frame). When those image inputs are wired, the node both feeds the pictures into Qwen3-VL and VAE-encodes them as `minimax_keyframes`. Do not rely on `<Picture N>` prompt tags, and do not use `MiniMaxH3ReferenceToVideo` on this graph.

Rules when graphs are added:

- One graph, one job. Do not mix smoke-test and production defaults in the same file.
- Record ComfyUI version, checkpoint names (D-02), canvas, frames, and steps in the graph filename or a sibling `.md`.
- Prompt text can stay parameterized. Weights stay outside git.
