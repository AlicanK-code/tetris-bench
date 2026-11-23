# Finding: single-seed scores mislabel functions, and `score` is the wrong curve variable

**Date:** 2026-11-20 · **Script:** `analysis/held_out.py`
**Held-out seeds:** 1000–1019 (20 seeds, disjoint from the 1/2/17/123 used so far)
**Cost:** zero generation time — every function was already on disk

Every score this project had reported came from the one piece sequence a function
was written against. This replays all ten saved functions on twenty sequences
they never saw. It is the project's first generalization measurement, and it
changes two conclusions.

---

## 1. Results

| function | seed 1 | held-out mean | sd | CV | min | max | pieces |
|---|---:|---:|---:|---:|---:|---:|---:|
| *baseline* heuristic | 21,600 | 20,915 | 1,563 | 7% | 14,700 | 21,900 | 494 |
| *baseline* random | 0 | 10 | 31 | 308% | 0 | 100 | 26 |
| qwen3-4b v1 | 0 | 20 | 70 | 348% | 0 | 300 | 22 |
| qwen3-4b v2 | 0 | 25 | 55 | 220% | 0 | 200 | 22 |
| qwen3-14b (×5, identical) | 400 | 110 | 107 | 97% | 0 | 400 | 29 |
| qwen3-30b run 1 | **0** | **325** | 402 | 124% | 0 | 1,600 | 40 |
| qwen3-30b run 2 | 1,700 | 1,530 | 1,304 | 85% | 0 | 4,800 | 70 |

---

## 2. Two reported numbers were wrong about the function

### 2.1 The 30B's "zero" function was not worthless

`noise-floor-qwen3-30b.md` recorded run 1 as scoring **0** and described it as
having an inverted height term that produced "not one completed row in the whole
game". On held-out seeds it averages **325** and reaches **1,600**.

The function is mediocre, not dead. Seed 1 happened to be a sequence it could not
clear a line on. The single-seed evaluation mislabelled it.

### 2.2 The 14B's 400 was its best case, not its typical one

Held-out mean **110**, with 400 as the *maximum* across twenty unseen sequences.
Seed 1 was the luckiest sequence of the twenty-one it has now played.

### 2.3 So the 30B's nondeterminism gap was overstated

The headline was 0 versus 1,700 — a 1,700-point spread from pure
nondeterminism. On held-out means the same two functions are **325 versus
1,530**, a gap of 1,205. The nondeterminism is real and still large; its
magnitude was inflated by about 40% by measuring on one sequence.

---

## 3. Seed noise dwarfs almost everything else

A *fixed, deterministic* function varies hugely across sequences it never saw:
coefficients of variation of **85% to 348%** for every model-written function.
Even the hand-written heuristic varies 7%, and that is suppressed by
right-censoring at the 500-piece cap.

For comparison, the generation noise measured on the 30B was 141% CV. Seed noise
is of the same order or larger, and until now only one of the two had been
measured. A single-seed score carries roughly as much uncertainty about a
function's quality as rerunning the model does.

Averaging over 20 seeds cuts this by about √20.

---

## 4. `pieces_placed` is the better curve variable

Measured as the ratio of between-function variance to mean within-function
(seed) variance — how well a variable separates real differences from noise:

| variable | between/within variance ratio |
|---|---:|
| score | 1.10 |
| **pieces placed** | **2.07** |

`pieces_placed` discriminates about **1.9× better**. The reason is structural:
score is driven by rare multi-line clears, so its variance explodes, and it has a
dead zone — any function that never completes a row scores exactly 0 however good
or bad its geometry is. Pieces placed is a smooth survival measure with neither
problem.

Note one thing this does *not* support: the worry that score has too many ties at
zero to show a curve. Averaging over twenty held-out seeds already removes that —
no function has a held-out mean of exactly 0. The case for `pieces_placed` is
discrimination, not ties.

---

## 5. The good news: the ladder orders correctly on held-out means

| rung | single-seed score | held-out mean score | held-out mean pieces |
|---|---:|---:|---:|
| qwen3-4b | 0 | 20–25 | 22 |
| qwen3-14b | 400 | 110 | 29 |
| qwen3-30b | 0 **or** 1,700 | 325 / 1,530 | 40 / 70 |

Single-seed scores gave 0, 400, and 0-or-1700 — barely an ordering. Held-out
means give a monotone gradient on both variables. The capability-ladder claim
looks considerably better under held-out evaluation than it did under
single-seed, which is the opposite of what one usually finds and is worth
stating plainly.

> **Later correction.** The monotone gradient does not survive a proper ladder.
> This table is three rungs at one-to-three samples each on `strategy_v2`, and it
> **omits the 8B** — which is exactly where the real ordering breaks. Measured
> with 15 independent chains per rung on `strategy_v3`
> ([size-ladder-is-a-step.md](size-ladder-is-a-step.md)), the 8B beats the 14B
> and the 4B, 8B and 14B are statistically indistinguishable from one another
> (every pairwise Fisher p >= 0.68). The gradient here is real within the three
> rungs it measured and is not evidence of a gradient across the family. What
> survives is the *method* claim — held-out evaluation beat single-seed — which
> is this document's actual subject.

---

## 6. What should change

1. **Report the curve on held-out mean, not training-seed score.** Free: replay
   costs under a second per seed.
2. **Use `pieces_placed` as the primary curve variable**, with score reported
   alongside.
3. **Hold seeds out of the loop.** `loop.py` currently runs a chain per seed and
   feeds each chain its own seed's outcomes, so every seed is a training seed.
   Feedback should average over ≥3 training seeds, with evaluation on a disjoint
   set of ≥10.
4. **Re-state the 30B nondeterminism gap** as 325 vs 1,530 on held-out means,
   keeping the 0 vs 1,700 single-seed figure as the illustration of why
   single-seed evaluation is inadequate.
