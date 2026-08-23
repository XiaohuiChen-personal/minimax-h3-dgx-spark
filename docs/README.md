# `docs/` — GitHub Pages site

Published URL: https://xiaohuichen-personal.github.io/minimax-h3-dgx-spark/

| Path | Role |
|---|---|
| `index.html` | Site hub |
| `briefing.html` | Research briefing (evidence) |
| `design/architecture.html` | Plain-language pipeline |
| `design/decisions.html` | D-01…D-14 |
| `design/optimizations.html` | Speed-ups and bans |
| `design/operator.html` | How a person and an agent use the server |
| `design/container.html` | Image contract and deploy steps |
| `assets/site.css` | Shared styles |
| `.nojekyll` | Stops Jekyll from rewriting pages |

Working source of truth is [`../design/`](../design/) markdown. Update markdown first, then the matching HTML. Deploy artifacts go in [`../deploy/`](../deploy/), not here.
