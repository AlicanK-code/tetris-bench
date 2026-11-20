# Finding: a feature-level counterexample fixed what outcome feedback could not

**Date:** 2026-11-20 · **Model:** `qwen3:14b` · **Training seed:** 1
**Script:** `analysis/counterexample_arm.py`
**Artifacts:** `runs/functions/counterexample/qwen3-14b-counterexample1.{py,json}`

The control arm is already recorded: given outcome feedback, two independent
revisions kept the broken hole count character-for-character and only changed
weights, with held-out performance flat
([first-revision-reweights-not-debugs.md](first-revision-reweights-not-debugs.md)).

This arm gave the **identical** outcome feedback plus one block: for a single
mid-game board, the true per-column heights and the true hole count. The prompt
is 5,299 chars against the control's 5,157, so a 142-char difference — prompt
length cannot explain the result.

---

## 1. Result

Held-out means over 20 unseen seeds, independently re-verified:

| function | held-out score | pieces | holes | hole condition fixed |
|---|---:|---:|---:|---|
| iteration 0 | 110 ± 107 | 29.1 | 85.8 | — |
| control A (outcome feedback) | 130 ± 108 | 30.6 | 82.2 | no |
| control B (outcome feedback) | 85 ± 81 | 27.8 | 88.0 | no |
| **counterexample** | **2,540 ± 1,060** | **101.5** | **28.7** | **yes** |
| *reference heuristic* | 20,915 ± 1,563 | 494.2 | 5.7 | — |

**A 23× improvement**, against a control that showed none. Pieces survived went
up 3.5×, holes down 67%. It is the first model-written function in this project
to beat the naive floor (1,675), and the best by a wide margin — the previous
best was the 30B's 1,530.

Still 8× below the reference, so this is not a solved game.

---

## 2. It fixed the hole count, correctly

```python
    for col in range(10):
        min_filled_row = None
        for row in range(20):
            if board[row][col]:
                min_filled_row = row
                break
        if min_filled_row is not None:
            for row in range(min_filled_row, 20):
                if not board[row][col]:
                    holes += 1
```

Find the topmost filled cell, then count every empty cell below it. That is
correct, and equivalent to `tetris_bench.metrics.holes`. The broken condition
`heights[col] > row` is gone.

It also reweighted heavily toward the now-meaningful term:
`lines * 1000 - holes * 100 - bumpiness * 50 - max_height * 20`.

---

## 3. The surprise: the definition it was handed is the one it ignored

The trace block contained prose defining column height — "measured from the
floor, so an empty column is 0 and a column whose topmost filled cell is in row 0
is 20" — **and** the labelled array `[2, 3, 4, 5, 6, 8, 8, 5, 5, 5]`.

It kept its fill-count heights anyway:

```python
        count = 0
        for row in range(20):
            if board[row][col]:
                count += 1
        heights[col] = count
```

So the bug it fixed (holes) was given to it as **a bare number with no
definition**. The bug it did not fix (heights) was given to it as **a definition
plus labelled data**. Exactly backwards from what one would predict.

That matters for attribution. The obvious objection to this arm is that the
trace block smuggles in a definition and so the result only shows a model can
apply a definition it was handed. The data does not support that objection: the
handed-over definition went unused.

A likely reason the heights bug was tolerable: once holes are penalised properly,
columns stay mostly solid, and for a solid column a fill count *equals* its
height. Fixing holes made the remaining bug largely harmless — which is itself an
argument that holes was the binding defect.

---

## 4. What this supports

**The bottleneck is credit assignment, not capability.** The 14B could fix this
bug all along. "You finished with 96 holes" does not localise it, because that
number is equally consistent with a correct hole count and a bad weight — which
is the reading both control revisions took. A single board with its true hole
count localises it immediately.

This reframes the headline. A flat improvement curve would not mean "this model
plateaus at Tetris". It would mean "outcome statistics are too indirect a signal
for this class of bug", and the loop's feedback channel would be the thing under
test as much as the model.

---

## 4b. Replication: 3 runs, 2 distinct functions, all fixed the bug

| run | source hash | output tokens | held-out score | hole bug fixed |
|---:|---|---:|---:|---|
| 1 | `1c739477c25a` | 8,495 | 2,540 | yes |
| 2 | `1c739477c25a` | 8,495 | 2,540 | yes |
| 3 | `0559210d9a42` | 7,401 | 2,540 | yes |

Runs 1 and 2 are byte-identical, so they are one sample rather than two. Run 3 is
a genuinely different generation: different variable names, reordered blocks, and
**all four weights scaled by exactly 10×**
(`1000/100/50/20` against `100/10/5/2`).

Uniform positive scaling cannot change an argmax, so the two are behaviourally
identical. Verified rather than assumed: across all 17 candidates for one board
the score ratio is exactly `{10.0}` and both pick the same placement — which is
why their held-out numbers agree to the digit.

So this is **2 independent generations, both of which derived the correct hole
count and the same relative weighting**. That is a real replication of the
qualitative result, and a stronger one than three identical samples would have
been.

Two incidental findings:

- The counterexample prompt is **reproducible** on this rung where the revise
  prompt is not: two of three generations came out byte-identical, and the third
  differed only by a scale factor. The revise prompt gave two different functions
  from two runs. A sharper constraint appears to produce more decisive token
  choices, so fewer near-ties for numerical noise to flip.
- The model converged on the same relative weighting twice from independent
  generations, which suggests the weighting is being derived rather than guessed.

## 5. Calibration

- **n=2 independent generations** for this arm against n=2 for the control. The
  qualitative result — bug fixed in 2/2 distinct functions versus untouched in
  2/2 controls — is solid. The effect size (23×) rests on a single behaviour,
  since both distinct functions play identically.
- **One rung, one iteration.** The 4B may lack the capability regardless, and the
  30B already produced a correct hole count unaided at iteration 0.
- The counterexample is **not** a diagnosis: it never says the hole count is
  wrong, which direction it scans, or what a hole is. It supplies measured values
  for one board.
- The reference remains 8× higher, so this is a large relative gain from a low
  base, not a solved problem.

---

## 6. What it changes

1. **Vary the trace content, not just re-roll the prompt.** All three runs used
   the identical prompt, so they probe generation variance, not robustness to
   *which* board the counterexample shows. If the effect only works for the board
   at piece 16, the result is much weaker. Same cost as what has been run.
2. **Try the other rungs.** The 4B may lack the capability regardless; the 30B
   already produced a correct hole count unaided at iteration 0, so it may have
   nothing to gain.
2. **This should probably become a loop variant, not the default.** An arm that
   supplies feature-level traces measures something different from one that
   supplies outcomes — and both are worth running, as the contrast *is* the
   result. Making it the default would quietly change what the benchmark claims.
3. **The null arm matters more now.** A 23× jump needs a no-feedback baseline
   beside it, or a reader cannot tell it from variance between generations.

---

## Appendix: two methodological notes from the failures

The first attempt at this experiment **timed out four times at 1,200s each**,
burning about 80 minutes. Ollama was healthy throughout; the 14B answers a short
prompt in 8 seconds.

The cause was the prompt. It had instructed the model to "work out what your own
code computes for these same boards, and compare", across two 20x20 boards. A
thinking model takes that literally and attempts to hand-trace a nested loop over
400 cells. Removing the instruction and using one board brought generation to
841s.

**Asking a model to self-trace induces an order of magnitude more deliberation
than asking it to revise.** Worth knowing before any prompt invites one.

Second note: retries are harmful here. A local generation that exceeds its budget
will exceed it again, and three retries turned a 20-minute failure into an
80-minute one. `max_retries=0` is correct for local experiments, and the client's
default of 3 is tuned for transient network faults that do not apply.
