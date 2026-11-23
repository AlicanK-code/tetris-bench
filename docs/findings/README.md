# Reading these write-ups

Each document here is one experiment, dated, with the generated functions kept as
artifacts under [`runs/published/`](../../runs/published/) so its claims can be
checked rather than taken on trust. They are written as they were found and
corrected in place with an indented **Later correction** block when a later
result overturns something, rather than being quietly edited — the sequence of
wrong turns is part of what the project is demonstrating.

Two conditions changed partway through and affect figures in several of the older
documents. Both are called out at each site, and explained once here.

## The "naive" baseline is no longer reproducible

Several early docs quote a **naive floor** — drop each piece as deep as it will
go — at 2,100 points on seed 1, or 1,675 as a mean. Those measurements were real
when taken, but **no such agent exists in the codebase now**, so the figure
cannot be reproduced from this repo and should be read as a historical marker
rather than a baseline you can re-measure. `grep -rn naive src/` returns nothing.

The two live reference players are `random` and `heuristic`, both in
[`src/tetris_bench/agents/`](../../src/tetris_bench/agents/) and both
reproducible:

```bash
uv run python analysis/baseline_ceiling.py
```

## The piece budget moved from 500 to 2,000

Docs dated before the change reason from a **500-piece** budget, where the
heuristic reference scores about **21,600** on seed 1 and 20,915 on held-out
means. At the current **2,000-piece** default the same heuristic averages
**84,720** on seeds 1000–1009 — roughly four times higher — because at 500
pieces it was being cut off rather than dying.

So a ratio quoted against 21,600 in an older doc understates the gap by about
4x, and any "N× below the reference" claim from that era should be read with its
budget in mind. Each doc's header states the budget it used.

This also means **censoring is the recurring methodological hazard** in this
project rather than a one-off: a capped game truncates exactly the runs that
would have gone long, which flatters a strong agent's consistency and compresses
the top of the scale. It has now distorted a headline figure more than once, most
recently the best function on the
[size ladder](size-ladder-is-a-step.md), censored in 8 of 10 games.
