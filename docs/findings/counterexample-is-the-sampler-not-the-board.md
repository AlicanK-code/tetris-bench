# A single draw cannot tell you which counterexample board works

**Status:** the first pass's per-board reading is withdrawn. The replication
that withdrew it then turned out to have a defect of its own, found immediately
afterwards, which changes what the numbers can support. Both corrections are
below. **The fire rate of this intervention is not yet estimated.**

## What was being tested

`analysis/counterexample_arm.py` shows the model a *trace board* — a snapshot
from a game its own function played — alongside the ordinary outcome feedback,
and asks for a revision. The control arm gets outcome feedback only.

The function being revised (`runs/functions/noise/qwen3-14b-noise1.py`) has the
project's signature defect: `heights[col] > row`, which has the board's
orientation backwards and so cannot see a gap. Iteration 0 scores **110** on the
held-out seeds, **3.8 points per piece**.

The first pass reported held-out **2540 / 120 / 5** for boards at piece 8 / 16 /
24 and was read as a per-board effect: board 8 informative, board 24 harmful.

## The defect in both passes: the sweep never varied the seed

`analysis/counterexample_arm.py` called `client.complete(messages)` without a
`seed`, so every run fell back to `config.seed`. `qwen3-14b` is configured
`seed: 1, temperature: 0.7`. **Every run on a given board therefore sent a
byte-identical request** — same prompt, same seed, same temperature. The run
index reached the output filename and nothing else.

So the right way to count the evidence is **six requests, one per board**:

| board | outputs | distinct functions | held-out scores of the distinct ones | holes |
|---|---:|---:|---|---|
| 4  | 3 | 2 | 20, 40 | 99.5, 100.5 |
| 8  | 4 | 3 | **2540**, **2455**, 130 | –, 37.6, 82.2 |
| 12 | 3 | 2 | 95, 145 | 91.3, 78.6 |
| 16 | 3 | 2 | 95, 105 | 88.2, 89.9 |
| 20 | 3 | 2 | 100, 100 | 85.7, 101.7 |
| 24 | 4 | 3 | 5, 65, **5835** | –, 93.8, 22.9 |

Plus three earlier outputs (2 distinct) at piece 16 that predate the
board-in-filename convention; only one of their scores, 120, survives in the
write-up. Iteration 0 for comparison: 110, holes 85.8.

**That identical requests gave different functions is not a contradiction.** This
rung is already known not to be bit-reproducible at a fixed seed — see
[seed-is-inert-at-temperature-zero.md](seed-is-inert-at-temperature-zero.md) —
from floating-point near-ties in long generations. Within each board, roughly
two of the three runs landed on the same completion and one diverged. Identical
output-token counts on the matching pairs confirm the same completion rather
than two generations that converged.

## What the data does and does not support

**Supported: a single draw per board cannot distinguish boards.** Board 24's one
request produced held-out **5** in the first pass and **5835** in the
replication — the worst and the best results in the project's history, from the
same bytes. Board 8's request produced 2540, 2455 and 130. Any design that shows
each board once is measuring generation noise and reporting it as a board
property, which is exactly what the first pass did.

**Supported: the intervention sometimes produces a large, real jump.** Three of
the 16 distinct functions cleared 20× the unrevised 110. The best is **33.1
points per piece** against iteration 0's 3.8, within sight of the hand-written
heuristic's 43.5. Nothing in the outcome-only control has come close: its two
revisions scored 130 and 85 against 110, both keeping `heights[col] > row`
verbatim and changing only weights.

> **Note (2026-11-25).** The heuristic reference is quoted here at 43.5, its
> rate run to exhaustion. The comparator this project now uses is **43.34**,
> the same player on the ten held-out sequences at the 2,000-piece budget
> that model results are measured in. The three figures it has been quoted
> at — 43.16, 43.34, 43.46 — are the same player under different conditions,
> and the spread is the honest measure of how stable the rate is. Nothing
> below changes; see [`baselines.py`](../../src/tetris_bench/baselines.py).


**Supported: the mechanism is visible in the holes column.** Both big winners cut
holes from 85.8 to 37.6 and 22.9. Every other sample stayed at 78–102 — it never
learned to see the gap at all, whatever it did to its weights. Of the 12 distinct
functions from the replication, the 5 that rewrote the `heights[col] > row`
comparison include both winners; none of the 7 that kept it verbatim scored
above 145. Fisher exact on 2/5 against 0/7 gives p=0.19, so this is a direction
and not a result — but it is the direction the mechanism predicts. Changing the
line is close to necessary; changing it *correctly* is the hard part.

**Not supported: any fire rate.** "3 of 16" is a rate over floating-point
divergence at one fixed seed, not over seeds. It is not an estimate of what the
intervention would do on a fresh sample, and it should not be quoted as one.

**Not settled: whether the board matters at all.** Board 8 produced 2 of its 3
distinct functions above 2400; the other five boards produced 1 big winner
between them, on board 24. Fisher exact gives p=0.07 one-sided. That is suggestive and
it is confounded with the per-board request being fixed, so it cannot be read
either way yet. The honest position is that the first pass's *specific* ranking
was noise, and whether any board ranking exists is an open question.

## Fixed

`counterexample_arm.py` and `null_arm.py` now derive a per-run seed through the
same `model_seed_for` the loop uses for chains, so a sweep index offsets the
configured seed exactly as a chain offset does. A regression test
(`tests/test_analysis_sweeps_vary_the_seed.py`) walks the AST of every script in
`analysis/` and asserts each `.complete(` call passes a `seed`, with an explicit
exemption list. `revise_reproducibility.py` is on that list and deliberately
unseeded: sending the identical request N times is its whole experiment.

**The loop's chains were never affected.** `loop.py` has always passed
`seed=model_seed_for(config.model_seed, position.chain)`, and all 30 positions
in `runs/published/five-chain/loop.jsonl` carry distinct `function_sha` values.
The independent-chains argument in CLAUDE.md stands; the defect was confined to
the standalone analysis sweeps, which bypass the loop's generation path.

## What this changes

- Estimating the fire rate needs a rerun on the fixed script — 6 boards × 3
  genuinely different seeds, ~4.2h on this hardware. Until then the arm is a
  demonstrated possibility with an unknown rate.
- The first pass is a worked example of a 3-sample sweep inventing structure.
  The replication is a worked example of the subtler version: 18 runs that look
  like a sample and are 6 requests.
- **Check the hashes before trusting a count.** Both errors here would have been
  caught in a second by hashing the outputs, which is now what the validity
  check in every write-up that rests on sample counts does.
