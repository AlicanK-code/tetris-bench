# Finding: a feature-level counterexample fixed what outcome feedback could not — on one trace board in three

**Date:** 2026-11-20 · **Model:** `qwen3:14b` · **Training seed:** 1
**Script:** `analysis/counterexample_arm.py`
**Artifacts:** `runs/published/counterexample/qwen3-14b-counterexample{1,2,3}.py`
(trace board at 16 pieces) and `-counterexample-p{8,24}-1.py` (the varied boards)

The title records what the arm was built to test. §4c records that it does not
generalise, and the two should be read together.

The control arm is already recorded: given outcome feedback, two independent
revisions kept the broken hole count character-for-character and only changed
weights, with held-out performance flat
([first-revision-reweights-not-debugs.md](first-revision-reweights-not-debugs.md)).

This arm gave the outcome feedback the control received plus one block: for a
single mid-game board, the true per-column heights and the true hole count.

> **Correction (see §4d).** The sentence that stood here — "the prompt is 5,299
> chars against the control's 5,157, so a 142-char difference — prompt length
> cannot explain the result" — was wrong, and wrong in a way that flattered the
> arm. That +142 was the **net of two changes**: the script also dropped the
> 418-character block that names the measured quantities. Measured by diff: 418
> removed, 560 added, 978 characters differing. All five generations in this
> document used that two-block prompt.

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

> **Conditions note.** Two of the numbers above are tied to conditions that have
> since changed, and both make this result look better than it is.
>
> The `naive` floor (1,675) came from an agent that no longer exists in the
> codebase, and the reference (20,915) is the heuristic at the old **500-piece**
> budget. At the current 2,000-piece budget the heuristic averages ~84,720, so
> "8× below the reference" is really about **33×**. See [README.md](README.md).
>
> The **23×** is also measured against a 110-point iteration-0 baseline generated
> under `strategy_v2`. On `strategy_v3` an unaided iteration 0 scores a held-out
> 1,580, so on pieces survived the advantage is 101.5 against 71.8 — roughly
> **1.4×, not 23×**. The qualitative finding (a feature-level counterexample
> fixed what outcome feedback could not, on one board in three) is unaffected;
> the multiplier is not quotable.

> **Read §4c before quoting this number.** The result replicates across
> generations on this trace board and **fails on two others**. One board out of
> three produced the fix; of the other two, one changed nothing and one produced
> a function that scored 5. The 23× is a property of a (prompt, board) pair, not
> of feature-level feedback in general.

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

## 4c. The effect does not survive changing the board

All three replication runs used the board after 16 pieces. Varying **only** that
board, one generation each, everything else identical:

| trace board | true holes | original line survived | held-out score | held-out holes |
|---|---:|---|---:|---:|
| after 8 pieces (sparse, max height 4) | 5 | no | **5** | 96.2 |
| after 16 pieces (×3 runs) | 17 | no | **2,540** | 28.7 |
| after 24 pieces (tall, max height 15) | 39 | **yes** | 120 | 87.0 |
| *iteration 0, for reference* | — | — | 110 | 85.8 |

Prompt lengths were 5,297 / 5,299 / 5,306 characters, so length explains none of
it.

**One board out of three produced the fix.** The piece-24 run kept the broken
line character-for-character, exactly as both outcome-feedback controls did — so
on that board the trace added nothing at all. The piece-8 run is the more
instructive failure: it *did* rewrite the hole count, into a different broken one.

```python
    for col in range(10):
        for row in range(20):
            if not board[row][col]:
                # Check if there's any filled cell below
                has_filled_below = False
                for r in range(row + 1, 20):
                    if board[r][col]:
                        has_filled_below = True
                        break
                if has_filled_below:
                    holes += 1
```

Row 0 is the top, so `range(row + 1, 20)` scans **downward**. This counts every
empty cell with something beneath it — the empty space *above* the stack. That is
the same error of direction the original made, re-expressed and far larger.
Measured against `tetris_bench.metrics.holes` rather than argued about:

| board | engine | piece-16 function | piece-8 function | original bug |
|---|---:|---:|---:|---:|
| after 8 pieces | 5 | 5 | 173 | 22 |
| after 16 pieces | 17 | 17 | 161 | 34 |
| after 24 pieces | 39 | 39 | 129 | 60 |

The piece-16 function is exactly right on every board. The piece-8 function is
wrong by an order of magnitude, and because its "hole" term grows with empty
space it rewards a taller stack — it penalises height while believing it
penalises holes. Held-out 5 against the 110 it was revising is a twenty-fold
regression. It also promoted `max_height` to the heaviest weight, so it
mismeasured the term it had just rewritten and then leaned on a different one.

### A string test reported this as a fix

The script printed `hole condition changed: True` for the piece-8 run, because it
tested only whether `heights[col] > row` was absent. For a while this read as 2
of 3 boards repairing the count. A string test cannot tell a fix from a fresh
bug. The check now reports whether the original line *survived* and nothing more;
the correctness evidence is the measured held-out hole average beside it — 28.7
for the working count, against 85.8 at iteration 0 and 96.2 for the inverted one.

### What it does to §4's claim

§4 said the bottleneck is credit assignment rather than capability, on the
grounds that the 14B could fix the bug once the error was localised. That reading
survives only in a much weaker form. A trace *can* localise the bug — the
piece-16 board did it twice from independent generations. But two thirds of the
boards tried did not, and one actively made things worse, so "a feature-level
counterexample fixes what outcome feedback cannot" is not supported as stated.
What is supported: **under at least one trace board the 14B produced a correct
hole count it never produced from outcome feedback.** That is a possibility
result, not an effect size.

Why the middle board might be the one that works is a hypothesis, not a finding:
at 16 pieces the stack has varied column structure *and* a hole count large
enough to be conspicuous, while the sparse board's 5 holes may be too small a
discrepancy to notice and the tall board's 39 may be swamped by a board where
almost every column is deep. Three points cannot distinguish that from chance.

---

## 4d. The prompt was not "the control plus a block"

`build_counterexample_prompt` passed `measurement_section=""`. The control's
`build_prompt` passes `MEASUREMENT_DECLARATION`, 418 characters, and
`declare_metrics` defaults to `True`. So the counterexample prompt **removed**
that block as well as adding the trace. Measured by building both prompts and
diffing them:

| | characters |
|---|---:|
| control | 5,157 |
| measurement declaration removed | −418 |
| trace block added | +560 |
| **net** | **+142** |
| **text that actually differs** | **978** |

Reporting +142 as "the difference" described a two-block manipulation as a
single addition. The docstring said "everything else identical"; it was not.

### Why this is worse than a bookkeeping error

`MEASUREMENT_DECLARATION` is not incidental. It was added in `f840a10`
specifically to remove a confound from the iteration 0→1 step: it names the
measured quantities at *every* iteration so that a rise between iterations
cannot be attributed to the model being handed a vocabulary it previously
lacked. An analysis script reintroduced exactly that confound, and nothing
caught it because the net length looked almost unchanged.

So the arm's manipulation was: *drop the block that names the quantities, add a
block that gives measured values for them.* That is a coherent treatment, but it
is not the one the document claimed, and it admits a reading nobody tested — the
active ingredient may have been the **removal**, not the counterexample.

### What is now true

The script passes the declaration, as the control does. Verified by diff: 0
characters removed, 560 added, one differing block — a pure insertion. The
prompt is consequently 5,717 characters, so **a replication will not reproduce
the five collected generations**, which is the correct trade: reproducing them
exactly would mean preserving the confound.

### What it does to the five generations on record

- **The board-variation comparison (§4c) is unaffected.** All three boards used
  the same builder, so that contrast is internally valid.
- **The counterexample-vs-control comparison is confounded.** Two blocks changed,
  so "the trace block caused the fix" is not isolated — even on the one board
  where a fix appeared.
- Both controls used the real `build_prompt`, so they *did* carry the
  declaration. The arm and its control therefore differed by more than intended
  in both directions.

Net effect on the headline: the arm demonstrated that *some* prompt change
produced a correct hole count on one board out of three. Which change, and why
that board, are both open.

---

## 5. Calibration

- **n=2 independent generations on one trace board** against n=2 for the control.
  On that board the qualitative result — bug fixed in 2/2 distinct functions
  versus untouched in 2/2 controls — holds. The effect size (23×) rests on a
  single behaviour, since both distinct functions play identically.
- **One board out of three.** §4c varied the trace board and the fix did not
  transfer: 2,540 / 120 / 5 across pieces 16 / 24 / 8. Across all five
  generations in this arm the count was repaired in 3 of 5, and in 1 of 3
  distinct trace boards. Treat the arm as showing that a trace *can* localise the
  bug, not that it reliably does.
- **Held-out variance is large and the samples are small.** One generation per
  new board. A spread of 2,540 to 5 between nominally equivalent prompts means no
  single number here is an estimate of anything, and the no-feedback null arm
  that would calibrate it has still not been run.
- **One rung, one iteration.** The 4B may lack the capability regardless, and the
  30B already produced a correct hole count unaided at iteration 0.
- The counterexample is **not** a diagnosis: it never says the hole count is
  wrong, which direction it scans, or what a hole is. It supplies measured values
  for one board.
- **The manipulation was two blocks, not one** (§4d), so even on the board where
  a fix appeared, the cause is not isolated to the trace.
- The reference remains 8× higher, so this is a large relative gain from a low
  base, not a solved problem.

---

## 6. What it changes

1. ~~**Vary the trace content.**~~ **Done, and the answer was no** (§4c). The
   effect is a property of a (prompt, board) pair. This was the cheapest
   available test of the headline and it was worth running before anything was
   built on top of it.
2. **The null arm is now the priority, not an afterthought.** Three nominally
   equivalent prompts produced 2,540, 120 and 5. Without a no-feedback baseline
   there is no scale on which to read any of them, and the possibility that
   re-prompting alone perturbs the function this much is wide open. It should run
   more than one generation.
3. **This must not become the loop's default.** It was already the plan to keep
   it a variant; §4c makes it a requirement. A treatment that helps on one board
   out of three and causes a twenty-fold regression on another would inject
   enormous variance into every curve the benchmark reports.
4. **Correctness checks must measure, not match.** The string test in
   `counterexample_arm.py` called a worse bug a fix. Any future arm should
   compare the generated function's features against `tetris_bench.metrics` on
   sample boards, which costs nothing and needs no model.
5. **Try the other rungs, but expect noise.** The 4B may lack the capability
   regardless; the 30B already produced a correct hole count unaided at
   iteration 0. With a 3-point spread this wide, one generation per rung will not
   settle anything.

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
