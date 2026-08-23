# `design/` — working notes

Markdown in this folder is the scratch pad for *how* we will deploy MiniMax H3 on DGX Spark. The public site shows skeletons until those notes are locked:

- [Operator (adopted)](https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/design/operator.html) — product end goal
- [Architecture (skeleton)](https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/design/architecture.html)
- [Decisions (skeleton)](https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/design/decisions.html)
- [Container (skeleton)](https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/design/container.html)

## Working files

1. [`operator.md`](operator.md) — SSH + agent + ComfyUI; one job at a time
2. [`architecture.md`](architecture.md)
3. [`decisions.md`](decisions.md)
4. [`container.md`](container.md)
5. [`optimizations.md`](optimizations.md)

When a decision is finalized, update the matching file here, then replace the skeleton HTML under [`../docs/design/`](../docs/design/). Do not start [`../deploy/`](../deploy/) work that contradicts an open item in `container.md`.
