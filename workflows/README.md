# `workflows/` — ComfyUI graphs

Empty on purpose. Versioned workflow JSON will live here once the host pipeline is proven.

Expected later files:

```text
workflows/
  h3-fl2va-smoke-5s17.json     # 960×544, 124 frames, 8 steps
  h3-fl2va-default-8s.json     # 960×544, 192 frames, 8 steps, SPAN 2×
```

Rules when graphs are added:

- One graph, one job. Do not mix smoke-test and production defaults in the same file.
- Record ComfyUI version, checkpoint names (D-02), canvas, frames, and steps in the graph filename or a sibling `.md`.
- These files are what the later container loads. Prompt text can stay parameterized; weights stay outside git.
