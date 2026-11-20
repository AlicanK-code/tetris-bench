# Finding: qwen3-30b is nondeterministic, with a 1,700-point noise floor

**Date:** 2026-11-19 · **Model:** `qwen3:30b-a3b` (MoE, ~3B active)
**Template:** `strategy_v2` · **Game seed:** 1 · **Model seed:** 1
**Temperature:** 0 · **Runs:** 2 · **Script:** `analysis/noise_floor.py`
**Artifacts:** `runs/functions/noise/qwen3-30b-noise{1,2}.{py,json}`

Companion to [the 14B result](noise-floor-qwen3-14b.md), which was fully
reproducible. This rung is not, and unlike `qwen3-4b` the nondeterminism reaches
the score.

---

## 1. Result

| run | source hash | generation | output tokens | reasoning | score | pieces | holes | moves with variation |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | `08868dc8fd4c` | 326s | 10,152 | 35,937 ch | **0** | 35 | 55 | 33/35 |
| 2 | `25238cd8083e` | 297s | 8,920 | 32,678 ch | **1,700** | 71 | 17 | 69/71 |

| | |
|---|---|
| distinct functions | **2 of 2** |
| score spread | **1,700** |
| stdev | 1,202 |
| coefficient of variation | **141%** |

Reference, same game seed: heuristic 21,600 · naive 2,100 · random 0.

**The noise floor on this rung is 1,700 points** — 81% of the naive floor, and
8% of the heuristic reference. An iteration-to-iteration gain smaller than that
is indistinguishable from nondeterminism.

> **Later correction.** Both figures above are single-seed. Replayed on 20
> held-out seeds ([held-out-seeds.md](held-out-seeds.md)), the same two functions
> average **325** and **1,530** — a gap of 1,205, not 1,700. Run 1 is mediocre
> rather than dead: it reaches 1,600 on sequences it can clear a line on, and
> seed 1 simply was not one. The nondeterminism is real and still large; its
> magnitude was inflated by about 40% by measuring on one sequence.

---

## 2. Determinism is not monotonic in model size

| rung | generations compared | distinct functions | score variance |
|---|---:|---|---|
| `qwen3-4b` | 4 | ≥2 | none (all 0 — every function was degenerate) |
| `qwen3-14b` | 5 | **1** | none (genuinely reproducible) |
| `qwen3-30b` | 2 | **2** | **1,700** |

Reproducibility has to be tested per rung. It cannot be inferred from size, and
the middle rung is the only reproducible one.

### 2.1 The MoE explanation holds up

`qwen3:30b-a3b` is mixture-of-experts: a gating network selects which experts
run per token, and that selection is itself a near-argmax over gate logits. A
last-bit numerical shift can therefore change *which experts process a token* —
a far coarser perturbation than flipping one output token among near-synonyms,
which is what happened on the 4B.

The evidence fits: the two runs differ by 1,232 output tokens (10,152 vs 8,920)
and 3,259 characters of reasoning. On the 4B, divergent runs stayed within ~220
characters of each other. This rung does not wander slightly; it takes a
different path.

---

## 3. What the two runs wrote

The two functions differ in exactly the way that matters most.

### 3.1 Run 2 (1,700 points) — a *correct* hole count

```python
    holes = 0
    for c in range(10):
        has_filled = False
        for r in range(20):
            if board[r][c]:
                has_filled = True
            elif has_filled:
                holes += 1
```

This is correct, and algorithmically identical to `tetris_bench.metrics.holes`:
scan a column top-down, and once a filled cell has been seen, count every empty
cell below it. **The first fully correct hole implementation from any model on
any rung.**

It is doing the real work. 17 final holes against the 14B's 96, and 71 pieces
survived against 35.

Its other terms largely saturate rather than help. Both `sum_heights` and
`heights` scan from `r=19` upward and break on the first filled cell, so they
find the **bottom-most** filled row, not the top. Once a column has anything on
the floor its contribution pins at 19 and stops varying, which makes the
bumpiness term inert after the opening moves. Harmless rather than damaging — but
it means 1,700 points came almost entirely from penalising holes correctly.

### 3.2 Run 1 (0 points) — an inverted height term

```python
    holes = 0
    for j in range(10):
        for i in range(1, 20):
            if not board[i][j] and board[i-1][j]:
                holes += 1
```

Nearly right: it counts empty cells with a filled cell *directly* above, so it
catches immediately-covered holes but undercounts stacked ones (a column of
`X . .` scores 1, not 2). Directionally sound.

```python
    sum_top = 0
    for j in range(10):
        top_row = 20
        for i in range(20):
            if board[i][j]:
                top_row = i
                break
        sum_top += top_row
    ...
    score_val = (lines_cleared * 1000000) - (holes * 10000) - (sum_top * 100) + col_val
```

`top_row` is the index of the topmost filled cell, 20 for an empty column. So
`sum_top` is **large when the board is empty** and small when stacks are tall.
Subtracting it therefore *rewards* a tall stack. The sign is inverted.

It also adds `col_term = 10 - abs(placement["column"] - 4)`, rewarding placement
near the centre — an invented heuristic with no clear justification, though at
magnitude 100 it is swamped by the others.

Result: 55 holes, 35 pieces, and not one completed row in the whole game.

### 3.3 This is the finding

Same model, same prompt, same seed, same temperature. One run derived a correct
hole count and scored 1,700. The other inverted its height term and scored 0.

**The difference between the best and worst model result in this project so far
is attributable entirely to nondeterminism**, not to model, prompt, iteration or
anything else under our control.

---

## 4. Consequences for Milestone 6

1. **Single-run iterations cannot support the headline claim on this rung.** With
   a 1,700-point floor, a curve rising from 0 to 1,500 over six iterations would
   be within noise.
2. **`regression count` is the most exposed derived metric.** On this rung it
   would largely count sampling variance. `iterations to plateau` is similarly
   unreliable.
3. **Multiple samples per iteration are required here**, with medians reported
   and the spread shown. That is affordable: MoE makes this the *fastest* rung at
   ~310s per generation, against the 14B's ~780s. Five samples per iteration is
   about 26 minutes; six iterations is roughly 2.6 hours per seed.
4. **Per-rung sampling strategy.** The 14B needs one run; the 30B needs several;
   the 4B needs one, since its scores are invariant even though its text is not.
   A uniform policy would either waste hours on the 14B or under-sample the 30B.

---

## 5. The silver lining

Run 2 is the best model result so far — 1,700 points, 71 pieces, 17 holes,
69/71 moves discriminating, and a correct hole count derived with no help. It is
within 20% of the naive floor and the first function that looks like a real
Tetris heuristic rather than an attempt at one.

Its weakness is now specific and nameable: height and bumpiness are measured
from the wrong end of the column and saturate. That is exactly the kind of defect
a feedback summary could target, and a strong candidate for the first thing the
improvement loop is tested on.

---

## 6. Open questions

1. How many samples per iteration on the 30B? The spread is from n=2; a proper
   estimate needs 5 or more.
2. Is `qwen3-8b` reproducible? It is the one untested rung.
3. Does the nondeterminism narrow once a function is good? Both 30B runs were
   early, exploratory attempts; a model revising a working function may have
   fewer genuine near-ties to flip on.
