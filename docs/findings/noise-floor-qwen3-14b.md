# Finding: qwen3-14b is reproducible, and writes a real strategy

**Date:** 2026-11-19 · **Model:** `qwen3:14b` · **Template:** `strategy_v2`
**Game seed:** 1 · **Model seed:** 1 · **Temperature:** 0 · **Runs:** 5
**Script:** `analysis/noise_floor.py`
**Artifacts:** `runs/published/noise-floor/qwen3-14b-noise{1..5}.{py,json}`

Purpose: measure how much the score varies across repeated identical requests,
since [the determinism finding](prompt-comparison-and-determinism.md) showed
`qwen3-4b` generations are not reproducible even with a fixed seed. Without that
number, an improvement curve cannot separate learning from noise.

---

## 1. Result: no noise to measure

| run | source hash | generation | output tokens | score | pieces | holes | moves with variation |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | `ad38961f3051` | 803s | 7,498 | 400 | 35 | 96 | 35/35 |
| 2 | `ad38961f3051` | 822s | 7,498 | 400 | 35 | 96 | 35/35 |
| 3 | `ad38961f3051` | 727s | 7,498 | 400 | 35 | 96 | 35/35 |
| 4 | `ad38961f3051` | 819s | 7,498 | 400 | 35 | 96 | 35/35 |
| 5 | `ad38961f3051` | 703s | 7,498 | 400 | 35 | 96 | 35/35 |

**All five runs produced the identical function, byte for byte** — one distinct
source hash, the same 7,498 output tokens every time. Score spread 0, stdev 0.

This is a stronger result than "zero score variance". On `qwen3-4b`, scores were
also identical across runs, but because several *different* functions all played
the same degenerate game. Here the generation itself is reproducible.

> **Later correction.** This result is **prompt-specific**. The revise prompt,
> 1.5x longer, is *not* reproducible on this rung: two revisions of the same
> function produced two different sources, though both scored the same. See
> [first-revision-reweights-not-debugs.md](first-revision-reweights-not-debugs.md).
> No rung is text-reproducible for revisions, and the `chains=1` policy for the
> 14B now rests on score stability from two samples rather than on this result.

**Determinism is model-specific, not a property of the setup.** `qwen3-4b`
diverges; `qwen3-14b` does not. Likely because the 4B produces longer traces
(~9,000 tokens vs 7,498) and is less decisive, so it encounters more near-ties
where a last-bit numerical difference can flip a token. This has to be verified
per rung rather than assumed — and `qwen3:30b-a3b` is the one most at risk, since
mixture-of-experts routing is itself a near-argmax decision over gate logits.

---

## 2. The function

```python
def score(board, placement):
    # Calculate column heights
    heights = [0] * 10
    for col in range(10):
        count = 0
        for row in range(20):
            if board[row][col]:
                count += 1
        heights[col] = count

    # Calculate max height
    max_height = max(heights)

    # Calculate number of holes
    holes = 0
    for col in range(10):
        for row in range(20):
            if not board[row][col] and heights[col] > row:
                holes += 1

    # Calculate bumpiness
    bumpiness = 0
    for i in range(9):
        bumpiness += abs(heights[i] - heights[i + 1])

    # Combine factors with weights
    lines_cleared = placement["lines_cleared"]
    return lines_cleared * 10 - max_height - holes - bumpiness * 0.5
```

This is recognisably the right shape: four features, sensible signs, a weighted
sum. It is the first function on the ladder that actually discriminates —
**35/35 moves had score variation, mean spread 6.89**, against the reference
heuristic's 6.83.
It cleared 4 lines for 400 points.

### 2.1 But it dies at 35 pieces with 96 holes

| player, seed 1 | score | pieces | holes |
|---|---:|---:|---:|
| heuristic reference | 21,600 | 500 | 2 |
| naive floor | 2,100 | 95 | — |
| **qwen3-14b** | **400** | **35** | **96** |
| qwen3-4b | 0 | 22 | 107 |

Better than random, still well below the naive floor.

> **Conditions note.** The `naive` figure comes from an agent that no longer
> exists in the codebase, and the heuristic figure here is at the old 500-piece
> budget (about 21,600 on seed 1) rather than the current 2,000, where the same
> heuristic averages ~84,720. Both conditions are explained in
> [README.md](README.md); ratios quoted against them understate the gap by
> roughly 4x.


> **Later correction.** 400 is this function's *best* case, not its typical one.
> On 20 held-out seeds it averages **110**, with 400 as the maximum — seed 1 was
> the luckiest of the twenty-one sequences it has now played. See
> [held-out-seeds.md](held-out-seeds.md).

### 2.2 Why: `heights` is a fill count, not a height

```python
count = 0
for row in range(20):
    if board[row][col]:
        count += 1
heights[col] = count
```

This counts *filled cells* in the column, not the column's height. A column with
blocks at rows 19 and 17 and a gap at 18 has height 3 but a count of 2. The two
agree only when a column has no gaps — which is exactly the situation the
function is supposed to help avoid.

### 2.3 Why: the hole count is inverted

```python
if not board[row][col] and heights[col] > row:
    holes += 1
```

`heights[col]` is a count; `row` is an index with 0 at the top. The condition
therefore flags empty cells whose row index is *below the fill count* — that is,
cells near the **top** of the board. Real holes sit beneath the topmost filled
cell, at high row indices.

Since filled cells accumulate at the bottom, for a column with `count` filled
cells this flags roughly the `count` empty cells at the top. So `holes`
approximates `sum(heights)` — aggregate height — and the function effectively
penalises height twice while never penalising an actual hole.

That is precisely what the game shows: 96 holes at 35 pieces, average 32.

### 2.4 Bumpiness is correct

The only feature it got right, and it inherits the `heights` bug.

---

## 3. What this establishes

1. **The benchmark is viable.** A rung exists that is reproducible *and* produces
   a genuine strategy. CLAUDE.md decision 3 holds here on the model side as well
   as the engine side.
2. **No noise threshold is needed for this rung.** An iteration-to-iteration
   difference on `qwen3-14b` is real by construction. The caveat is that this must
   be re-verified per rung, and `qwen3-4b` already fails it.
3. **The 14B is the right rung to develop Milestone 6 against.** It discriminates,
   scores non-zero, and is reproducible, so a change in the curve is attributable
   to the loop rather than to sampling.
4. **Geometry-only is vindicated.** The model derived height, holes and bumpiness
   unprompted — the concepts were never given to it. It simply implemented two of
   the three incorrectly. That is a far more interesting failure than reweighting
   supplied features would have been, and it leaves an enormous gap (400 vs
   21,600) for iteration to close.
5. **The improvement loop has a specific, learnable target.** "You finished with
   96 holes" points directly at the inverted hole condition. If a revision fixes
   that comparison, the score should move substantially — which is the cleanest
   possible demonstration of the thing this benchmark exists to measure.

---

## 4. Cost

Five runs, 703–822s each: **about 64 minutes** for one rung at one iteration.
Scaling to six iterations across four rungs and three seeds is tens of hours.
Milestone 6 needs checkpointing and resumability, and should probably develop
against the 14B at one seed before any full sweep.

---

## 5. Open questions

1. Is `qwen3-8b` reproducible? **The 30B is not** — see
   [noise-floor-qwen3-30b.md](noise-floor-qwen3-30b.md): two runs, two different
   functions, scoring 0 and 1,700. Determinism is not monotonic in size, and the
   14B is so far the only reproducible rung.
2. Does the 4B's nondeterminism matter in practice, given its scores are
   invariant anyway? Possibly not, which would mean the problem is confined to a
   rung whose curve is flat at zero regardless.
3. ~~Should the loop's feedback name the metric ("96 holes") or the suspected
   cause ("your hole count flags cells near the top of the board")?~~
   **Decided: the metric.** "Feedback is symptoms, not diagnoses" in
   `CLAUDE.md` — the model must diagnose its own bug, because that is the
   ability being measured. One mechanical exception survives, for a function
   that scored every candidate identically.
