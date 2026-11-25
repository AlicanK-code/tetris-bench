# Figures

The pictures the top-level README shows, kept here rather than in
`analysis/figures/` — which is gitignored — so that **each figure sits beside
the log it is drawn from.** A commit that changes a run's data and a commit that
changes its picture are then the same commit, which is the structural answer to
the staleness the gitignore comment warns about: a 14B curve once sat in the
scratch directory for two runs after both missing rungs had been measured.

Nothing here is a source of anything. Every file regenerates from the published
logs in a few seconds, with no model involved:

```bash
for run in 4b-loop 8b-loop five-chain 30b-pilot; do
  uv run python analysis/plots.py --log runs/published/$run/loop.jsonl --out runs/published/figures
done
```

```bash
uv run python analysis/power_figure.py --out runs/published/figures
```

```bash
uv run python analysis/comparison_figure.py
```

The comparison figure reads `../replayed-at-canonical.json`, the cached replay
of all 229 published functions under the canonical conditions. Regenerate the
cache itself with `--replay`; it takes about ten minutes and needs no model.

| file | what it shows |
|---|---|
| `functions-vs-baselines.png` | Every published function replayed under one set of conditions — the ten held-out sequences at the 2,000-piece budget — against random play and the hand-written heuristic. The distribution is the result: the spread inside one model is far wider than any gain the loop produced. |
| `power-four-rungs.png` | Each rung's median gain against the gain its run could have detected at 80% power, from that rung's own paired σ. The project's headline in one image: four bounded nulls, none clearing its bar. |
| `curve-qwen3-4b.png` | 5 chains × 6 iterations, the second rung measured. |
| `curve-qwen3-8b.png` | 10 chains × 6 iterations, the best-powered curve here. |
| `curve-qwen3-14b.png` | 5 chains × 6 iterations, the first rung measured. |
| `curve-qwen3-30b.png` | 6 chains × 6 iterations, the power pilot. |

## The two conventions, which do not agree

The four curve figures come from `Curve`, which scores a **rejected generation
as a real zero** and reports the **gain of the medians**. The tables in the
findings exclude rejected positions and report the **median of the per-chain
gains**. On the 8B that is 8.3 → 17.0 against 15.63 → 17.04; on the 30B it is
−5 against +7.37.

Both are defensible — a rejection genuinely produced no function, and it
genuinely is not a measurement of one — and neither is the other's error. What
would be an error is quoting one number with the other's label, so each figure's
title says which it is drawing, and so does this file.
