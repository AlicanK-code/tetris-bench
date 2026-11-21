# Finding: the first revision reweighted instead of debugging

**Date:** 2026-11-20 · **Model:** `qwen3:14b` · **Template:** `strategy_v3`
**Training seed:** 1 · **Runs:** 2 independent revisions of the same function
**Script:** `analysis/revise_reproducibility.py`
**Artifacts:** `runs/published/revise/qwen3-14b-revise{1,2}.py`

This is the project's first evidence on its own headline question. It was
collected as a side effect of testing something else, and it is a negative
result on one rung at one iteration.

---

## 1. What was being tested

Whether reproducibility measured on the *iteration-0* prompt transfers to the
*revise* prompt, which is 1.5× longer (5,157 chars vs 3,529). The whole sweep
budget rested on that transfer: `chains=1` for the 14B.

Method: take the 14B's own saved function, replay it to build a genuine feedback
summary, build the real iteration-1 prompt, generate the revision twice.

| run | source hash | time | output tokens | reasoning | score (seed 1) |
|---:|---|---:|---:|---:|---:|
| 1 | `4d15f39cca7b` | 476s | 6,002 | 23,654 ch | 300 |
| 2 | `4ab442299b33` | 488s | 5,611 | 22,737 ch | 300 |

---

## 2. On the reproducibility question: text diverges, score does not

**Two distinct revisions.** So iteration-0 reproducibility does **not** transfer
to the revise prompt. The review's warning was correct: reproducibility is a
property of the *(model, prompt)* pair, and nothing licensed the transfer.

But both scored **300**, spread 0. That is the 4B's pattern, not the 30B's — the
text diverges while the outcome does not.

So the honest status of each rung is now:

| rung | iteration-0 text | revise text | score variance |
|---|---|---|---|
| `qwen3-4b` | diverges | — | none (all degenerate) |
| `qwen3-14b` | **reproducible** | **diverges** | none observed (n=2) |
| `qwen3-30b` | diverges | — | **1,700** single-seed / 1,205 held-out |

**No rung is text-reproducible for revisions.** The "14B is reproducible" result
was prompt-specific, and `CLAUDE.md`'s claim that it "needs one chain" rests on
score stability from two samples, which is weak evidence. It is not yet wrong,
but it is not established either.

The verdict logic in `revise_reproducibility.py` originally read "not
reproducible ⇒ needs several chains". That conflated text divergence with score
divergence, and only the second threatens a curve. It now distinguishes the three
cases, as `noise_floor.py` already did.

---

## 3. The more important finding: it changed the weights, not the bug

Iteration 0's function had a specific, identified defect — a hole count that
flags cells near the **top** of the board rather than beneath the stack, so it
approximates aggregate height and never penalises an actual hole
([noise-floor-qwen3-14b.md](noise-floor-qwen3-14b.md) §2.3). The feedback told it
the game ended with 96 holes.

**Both revisions kept that line character-for-character:**

```python
    for col in range(10):
        for row in range(20):
            if not board[row][col] and heights[col] > row:
                holes += 1
```

What changed was only the weighting:

| version | weighted sum |
|---|---|
| iteration 0 | `lines * 10 - max_height - holes - bumpiness * 0.5` |
| revision A | `lines * 100 - max_height * 10 - holes * 5 - bumpiness * 2` |
| revision B | `lines * 100 - max_height * 5 - holes * 10 - bumpiness * 2` |

The `heights`-as-fill-count bug (§2.2 of the same document) also survived
untouched in both.

Told "you finished with 96 holes", the model concluded **"penalise holes more"**
rather than **"my hole count may be wrong"**. Two independent draws did the same
thing, which makes this a qualitative finding rather than a single sample.

---

## 4. And it did not improve

Held-out means over 20 unseen seeds, which is the variable that matters rather
than the training seed:

| function | held-out score | pieces | holes | steering |
|---|---:|---:|---:|---:|
| iteration 0 | 110 ± 107 | 29.1 | 85.8 | 81% |
| revision A | 130 ± 108 | 30.6 | 82.2 | 84% |
| revision B | 85 ± 81 | 27.8 | 88.0 | 81% |

One revision slightly up, one slightly down, both far inside the ±107 noise. The
mean of the two revisions is 107.5 against iteration 0's 110. **No improvement.**

On the training seed it looks like a regression, 400 → 300 — but 400 was that
function's luckiest sequence out of twenty-one, so the training-seed number is
the wrong one to read. Held-out says flat, not worse.

---

## 5. What this means, with the calibration it deserves

The methodology review predicted exactly this: outcome feedback is an extremely
indirect signal for a scan-direction or indexing bug. "96 holes" is consistent
with a correct hole count and a bad weight, which is the reading the model took.
Nothing in the feedback distinguishes that from a miscount.

So the first evidence says the loop produces **weight tuning, not debugging** —
which, if it holds, reframes the headline. A flat curve would not mean "this
model plateaus at Tetris". It would mean "this model cannot locate an off-by-one
in its own code from aggregate outcome statistics", which is a different and
arguably more interesting claim.

**What this is not:** conclusive. It is one rung, one iteration, two draws.
Six iterations might get there; a model that reweights at iteration 1 may
re-examine its arithmetic at iteration 3 when reweighting visibly fails. That is
precisely the experiment still to run.

---

## 6. What it changes

1. **`CLAUDE.md`'s per-rung chain policy is not established.** The 14B's
   `chains=1` rested on iteration-0 reproducibility, which does not transfer.
   Needs more revision samples before the sweep, or chains everywhere.
2. **The counterexample arm is now the highest-value experiment in the backlog.**
   If a model repairs the bug instantly when shown a *feature-level* trace —
   "your `heights` array was [2,0,0,…]; the true heights are [3,1,0,…]" — but
   never from outcome feedback, the finding is that the loop's bottleneck is
   credit assignment rather than model capability. One generation per rung.
3. **Report held-out, never training-seed.** The training seed said 400 → 300, a
   25% regression. Held-out says flat. The former would have been a wrong
   headline.
