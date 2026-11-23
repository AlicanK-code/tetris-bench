# The 4B loop reweights a crashing function five times

**Date:** 2026-11-23 · **Model:** `qwen3:4b` · 5 chains × 6 iterations, 2 h 22 m
**Unit:** points per piece on held-out seeds 1000-1009; train seeds 1, 2, 17 fed back
**Sources:** [`runs/published/4b-loop/`](../../runs/published/4b-loop/)

The second rung ever taken past iteration 0, and the first independent test of
whether this project's improvement findings are about *the loop* or about *the
14B*. 30 generations, 243,280 output tokens, 282.8 s per generation.

**Three results, in descending order of how much they change.**

---

## 1. The 4B does not improve, and the run cannot prove it

| chain | it0 | it1 | it2 | it3 | it4 | it5 | gain |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 1.29 | 4.66 | 4.66 | 4.42 | 4.69 | 4.69 | **+3.40** |
| 1 | 0.61 | 4.13 | 4.19 | 4.64 | 5.26 | 13.05 | **+12.44** |
| 2 | 8.25 | 8.92 | 7.28 | 7.14 | 8.25 | 0.00 | **−8.25** |
| 3 | 7.49 | 0.44 | 0.44 | 0.44 | 0.44 | 0.44 | **−7.05** |
| 4 | 8.35 | 0.27 | 3.14 | 10.47 | 0.67 | 3.72 | **−4.63** |
| **median** | **7.49** | 4.13 | 4.19 | 4.64 | 4.69 | **3.72** | **−3.77** |

The median curve **falls**, 7.49 → 3.72. Three of five chains ended below where
they started and two of those collapsed to near-zero.

**It is not a significant fall.** The measured paired standard deviation is
**8.69**, so the minimum detectable change at five chains is **10.88** — far
larger than the 3.77 observed. The correct reading is **no detectable change**,
with a point estimate that leans negative. "The loop harms the 4B" is not
supported, and neither is any improvement.

**The starting point replicates, so the shape is not a sampling accident.** This
run's iteration 0 median is **7.49** against the ladder's **7.36** measured
independently on 15 chains, with comparable spread (3.90 against 4.43). The
chains began where this rung is known to begin and went nowhere from there.

---

## 2. A chain carried a fatal bug through five revisions while tuning its weights

Chain 3 is the result worth the whole run. Its iteration-0 function scored 7.49.
Its first revision introduced this:

```python
def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    total_empty = total_empty(board)      # <-- shadows the function it calls
```

Assigning `total_empty` inside `score` makes the name local to `score`, so the
call on the same line raises `UnboundLocalError` before it can return anything.
**Every scoring call failed: 342 sandbox failures per game**, at every one of
iterations 1 through 5.

The model was told. The revise prompt quotes the interpreter verbatim, three
times, naming the variable:

```
- placement 0: UnboundLocalError: cannot access local variable 'total_empty'
               where it is not associated with a value
```

What the 4B did with that, across five consecutive attempts, was **change the
coefficients around the broken line and keep the broken line**:

| iteration | the weights it moved | the bug |
|---|---|---|
| 1 | `lines*100`, `(20−max_height)*25`, `(100−total_empty)*3` | unchanged |
| 2 | `lines*1000`, `total_empty*5` | unchanged |
| 3 | sign flipped to `−total_empty*5`, added `bottom_empty*3` | unchanged |
| 4 | `−total_empty*50`, `bottom_empty*10` | unchanged |
| 5 | `−total_empty*55`, `(20−max_height)*35`, added `top_empty*25` | unchanged |

Five distinct functions — all 30 positions in this run have distinct SHAs, so
nothing was cached or replayed — each a different weighting of an expression
that has never once produced a number.

**This sharpens the project's existing "first revision reweights instead of
debugging" finding considerably.** That one was about a *semantic* bug (a hole
count that counted empty cells) under *outcome-only* feedback, where the
argument "the model was not told what was wrong" is available. Here the bug is
fatal rather than subtle, the feedback contains the interpreter's own diagnosis
naming the exact variable, and the model still only reaches for the weights.
The failure is not a missing-information failure. **The harness told it; it
could not act on the telling.**

---

## 3. My own power prediction for this rung was wrong by a factor of 8 in n

Recorded because it was used to justify running this rung at five chains.

The prediction was made from the ladder's **cross-chain spread of 4.43**,
scaled by 0.70 — the ratio measured on the 14B, where iterations within a chain
share a lineage and so vary *less* than two independent generations do.

| | predicted | measured |
|---|---:|---:|
| paired standard deviation | 3.10 | **8.69** |
| minimum detectable gain at n=5 | 3.88 | **10.88** |
| chains needed for a +8.04 gain | 1.2 | **9.2** |

**On the 4B the ratio inverts.** Paired σ_d is **2.39×** the cross-chain spread,
where on the 14B it is **0.70×**. So the scaling assumption underneath the 30B
power analysis — that the paired figure is the smaller one — is a property of
the 14B and not of the method.

Why it inverts is visible in the table in §1: on this rung a single revision can
move a chain from 8.35 to 0.27 and back to 10.47. Iterations within a 4B chain
do *not* share a stable lineage, because a revision frequently replaces the
function wholesale or breaks it. Low cross-chain spread measured a floor effect —
every chain starts near-equally bad — and said nothing about how violently a
chain moves once the loop starts.

**The practical consequence:** the 30B's requirement of 14-28 chains rests on
the same 0.70 scaling and is now known to be the optimistic end of a range that
can go the other way. Any rung's paired σ_d has to be measured on that rung.

---

## 4. The two collapses, for the record

- **Chain 3** is §2: a crash carried through five revisions.
- **Chain 2** survived five iterations around 7-9 and then scored **0.00** at
  iteration 5, by writing `+ max_col_height * 30` — rewarding height. An
  inverted sign on the term that matters most, which is the same failure mode
  recorded in [the ladder write-up](size-ladder-is-a-step.md); its
  `total_holes` also counts every empty cell rather than holes, the conflation
  that [the 4B's iteration-0 study](qwen3-4b-iter0-detailed.md) found on every
  rung.

Only **1 of 30** positions scored exactly zero, but **9 of 30** scored under
1.0 point per piece, which on this rung is the same thing in practice.

---

## 5. What this does and does not establish

**Establishes:** the loop produces no detectable gain on a second rung; the
earlier improvement findings are not obviously general; a crashing function with
its traceback quoted back can survive five revisions of a 4B; and paired σ_d
must be measured per rung rather than scaled.

**Does not establish:** that the loop fails in general. Five chains at a
measured σ_d of 8.69 can only see changes above 10.88, and the 4B is the rung
with the least room — its honest headroom is the 8.27 to its own best ladder
chain, not the 36.14 to the hand-written heuristic. A rung with room and a
quieter paired term could still show a gain. **The 8B remains the better
experiment, and this run slightly strengthens that**: it demonstrates that
"quiet at iteration 0" does not mean "cheap to measure through the loop".

**Tested since:** the zeros-and-crashes rate was the obvious candidate for the
real effect on this rung, and it is null too — 5 revivals against 5 deaths
pooled with the 14B, p = 1.000 — with the sample size that would have been
needed now measured at 15-55 chains against the 5 that ran. See
[the-zeros-rate-does-not-move-either.md](the-zeros-rate-does-not-move-either.md).

---

## 6. Reproducing it

The analysis is replay and arithmetic, sub-second. The run itself is 2 h 22 m.

```bash
uv run python - <<'PY'
import json, math, statistics
from tetris_bench.curves import build_curves
rows = [json.loads(l) for l in open("runs/published/4b-loop/loop.jsonl")]
(c,) = build_curves(rows)
for ch in sorted(c.chains):
    r = [p.headline for p in c.chain_series(ch)]
    print("chain %d %s gain %+6.2f" % (ch, " ".join("%6.2f" % x for x in r), r[-1] - r[0]))
d = [c.chain_series(ch)[-1].headline - c.chain_series(ch)[0].headline for ch in sorted(c.chains)]
print("median gain %+.2f  paired sd %.2f  cross-chain sd %.2f"
      % (statistics.median(d), statistics.stdev(d), c.chain_spread()))
print("MDE at n=5: %.2f" % (2.8 * statistics.stdev(d) / math.sqrt(5)))
PY

# The crash, and the feedback that named it
grep -n "total_empty = total_empty" runs/published/4b-loop/functions/*.py
uv run python -c "import json; print(json.load(open(
  'runs/published/4b-loop/functions/qwen3-4b-chain3-iter5.json'))['prompt'])" | grep UnboundLocal

# The run
uv run tetris-bench loop --model qwen3-4b --chains 5 --iterations 6 \
    --log runs/4b-loop/loop.jsonl --save-dir runs/functions/4b-loop
```
