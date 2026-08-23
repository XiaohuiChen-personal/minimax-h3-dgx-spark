# Design — what to build

These notes are the contract. An implementing agent should be able to read them and then write the workflows, scripts, and Docker image **without inventing a new stack**.

Read in this order:

1. [`architecture.md`](architecture.md) — what the machine does, in plain language
2. [`decisions.md`](decisions.md) — the numbered choices (D-01…D-14)
3. [`optimizations.md`](optimizations.md) — what to speed up, and what never to turn on
4. [`operator.md`](operator.md) — how a person and an agent use the running server
5. [`container.md`](container.md) — how to build and start the Docker image

Public HTML (same content, for humans):

- [Architecture](https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/design/architecture.html)
- [Decisions](https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/design/decisions.html)
- [Optimizations](https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/design/optimizations.html)
- [Operator](https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/design/operator.html)
- [Container](https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/design/container.html)

Evidence behind the numbers lives in the [research briefing](https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/briefing.html). Do not reopen a locked decision without new measurements on this GB10.

## What is already decided

The product is: SSH into a DGX Spark, ask Cursor or Claude to generate, get an mp4. One GPU job at a time. ComfyUI stays up. The graph is predefined.

The next implementation step (not this folder) is:

- `workflows/h3-fl2va-smoke-5s17.json`
- `workflows/h3-fl2va-default-8s.json`
- `scripts/` download, check-weights, submit/poll, smoke-test
- `deploy/Dockerfile` and `deploy/compose.yaml`

Those files must follow this design. They must not invent a different model, canvas, or serving stack.
