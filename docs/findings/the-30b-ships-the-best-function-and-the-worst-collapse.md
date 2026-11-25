# The 30B ships the best function in the project and its worst collapse

**Date:** 2026-11-24 · **Model:** `qwen3:30b-a3b` (MoE, ~3B active)
**Unit:** points per piece (`eval_rate`), 2,000-piece budget, 10 held-out seeds
**Run:** 6 chains x 6 iterations, 36 generations, 3 h 42 m wall clock
**Source:** `runs/published/30b-pilot/loop.jsonl`

This run was commissioned as a **power pilot**, not as an attempt to show
improvement. Every power claim in this repo used a paired standard deviation
*scaled* from the 14B, and the 4B had already shown that the scaling can invert.
The pilot's job was to measure the 30B's paired term directly.

It did, and the answer demotes a published figure. It also produced the two
best functions the project has ever recorded and a chain that declined
monotonically for five revisions, which is the more interesting result.

---

## 1. The curve

Held-out rate per position, 10 unseen seeds each. Chain 2 has no iteration 1 --
see [section 5](#5-a-failure-class-the-repo-did-not-have).

| chain | it0 | it1 | it2 | it3 | it4 | it5 | gain |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 38.3 | 41.7 | 32.4 | 39.4 | 40.0 | **47.0** | +8.70 |
| 1 | 41.6 | 42.2 | 28.6 | 33.2 | 43.7 | **50.2** | +8.64 |
| 2 | 39.4 | — | 36.3 | 32.2 | 21.3 | 13.5 | **−25.91** |
| 3 | 38.8 | 38.4 | 25.9 | 22.9 | 32.2 | 25.4 | −13.44 |
| 4 | 0.0 | 0.4 | 14.2 | 1.4 | 29.2 | 19.2 | +19.17 |
| 5 | 35.5 | 43.5 | 43.2 | 48.4 | 41.8 | 41.6 | +6.10 |
| **median** | **38.57** | 41.66 | 30.51 | 32.70 | 36.12 | **33.51** | **+7.37** |

The median gain is **+7.37** against a minimum detectable gain at n=6 of
**19.16**. So this is a **third rung with no detectable change**, after the 14B
(+8.04, itself inside its own noise) and the 4B (−3.77).

Note the median *falls* from iteration 0 to iteration 5 while the median
first-to-last gain is positive. Both are correct: the median of the gains is not
the gain of the medians, and with 6 chains and a σ_d of 16.76 neither is a
measurement of anything.

---

## 2. What the pilot was for: σ_d, measured

| estimate | value | basis |
|---|---:|---|
| scaled from the 14B | 10.54 | 8.74 x 15.13/12.55, the published figure |
| conservative proxy | 15.13 | the ladder's cross-chain spread |
| **measured here** | **16.76** | the 6 chains' own first-to-last differences |

**The scaled estimate was too low by 1.59x**, and it is the one the repo
published. The consequence for the run it was used to cost:

| target | with σ_d = 10.54 | with σ_d = 16.76 |
|---|---:|---:|
| chains for a +8.04 gain | 13 | **34** |
| chains for heuristic parity (17.52) | 5 | 8 |

So the headline sentence of
[30b-loop-is-underpowered-not-futile.md](30b-loop-is-underpowered-not-futile.md)
-- "a properly aimed 30B loop needs 14–28 chains" -- becomes **34 chains, about
19.6 hours**. The run was affordable; the published sample size was not the
right one.

### The ratio does not scale

The reason to measure rather than scale, in one table:

| rung | paired σ_d | cross-chain σ | ratio |
|---|---:|---:|---:|
| `qwen3-14b` | 8.74 | 12.55 | **0.70x** |
| `qwen3-30b` | 16.76 | 15.93 | **1.05x** |

> **Correction 2026-11-24 (later the same day).** This ratio uses the standard
> deviation of the iteration-0 rates as its denominator, where the 4B's 2.39x
> and the 14B's 0.70x use `Curve.chain_spread()` -- the project's own statistic,
> which averages the between-chain spread over every iteration. Two definitions
> of one denominator, compared across runs. Under `chain_spread()` throughout,
> the four measured rungs read **0.70x (14B), 0.84x (8B), 1.07x (30B) and 2.39x
> (4B)**. The conclusion is unchanged -- the span is 3.4x either way -- but the
> mixed denominator is the kind of error that makes a cross-run comparison mean
> nothing, so it is recorded here rather than quietly fixed.
| `qwen3-4b` | 8.69 | 3.63 | **2.39x** |

Three rungs, three ratios, spanning 3.4x. There is no constant here to borrow,
so **every future power claim in this project has to measure its own σ_d or
state that it is guessing.** That is the pilot's actual deliverable.

---

## 3. Refinement: the loop's first real chance, and nothing

Both completed loops ran on rungs where most first attempts are already broken,
so the capability probes could only ever measure *repair*. The 30B starts
**4 of 6 probe-clean**, so this is the first run where the loop had working
functions to improve.

| | it0 | it1 | it2 | it3 | it4 | it5 |
|---|---:|---:|---:|---:|---:|---:|
| probe-clean | 4/6 | 4/5 | 6/6 | 4/6 | 5/6 | 4/6 |

**It starts at 4 of 6 and ends at 4 of 6.** Within chains: **3 repairs against 3
regressions over 28 transitions.** Pooled across all three loops the count is
now 4 repairs against 5 regressions over 68 transitions.

> **Superseded 2026-11-24 (later the same day):** the 8B loop added 50 more
> transitions, so the pooled counts here and in §7 below are out of date. Over
> all four rungs: **10 repairs in 83 chances against 9 regressions in 50**, and
> **130 zeros-rate transitions with 14 revivals against 11 deaths, p = 0.690**.
> Both still null. See
> [the-best-powered-null-and-the-inert-revisions.md](the-best-powered-null-and-the-inert-revisions.md).

And among the chains that were probe-clean at both ends -- the ones with
nothing to repair, where only refinement was available:

| | chains | mean gain |
|---|---|---:|
| probe-clean throughout | 0, 2, 3 | **−10.22** |
| not | 1, 4, 5 | **+11.30** |

The sign is the wrong way round for a refinement story, but **it is not
significant: exact permutation p = 0.300** over all 20 splits, which with three
chains a side is the smallest p this design can produce short of a clean sweep.
It is recorded because it is the only direct evidence either way, not because it
shows the loop harms working functions.

---

## 4. The two mechanisms, side by side

This run contains the clearest example the project has of a revision working,
and the clearest of one destroying a function. Both are reweightings.

### Chain 1: correct reweighting, +8.64 to the best score recorded

```python
# iteration 0 -> 41.6
return lines * 100 - holes * 20  - max_height * 5  - bumpiness      + unique_term
# iteration 5 -> 50.2
return lines * 10  - holes * 350 - max_height * 15 - bumpiness * 35
```

The hole penalty rises **17.5x** and the line reward falls **10x**. The model
got there from outcome feedback alone, in five steps, ending **above the
hand-written heuristic's 43.5**.

> **Note (2026-11-25).** The heuristic reference is quoted here at 43.5, its
> rate run to exhaustion. The comparator this project now uses is **43.34**,
> the same player on the ten held-out sequences at the 2,000-piece budget
> that model results are measured in. The three figures it has been quoted
> at — 43.16, 43.34, 43.46 — are the same player under different conditions,
> and the spread is the honest measure of how stable the rate is. Nothing
> below changes; see [`baselines.py`](../../src/tetris_bench/baselines.py).


> **Amended 2026-11-24 (later the same day).** This paragraph used to add "that
> is the direction the classic Tetris weightings go -- survive, do not chase
> lines", offering the direction as the account of why the revision worked. The
> 8B loop produced a counterexample the same night: its chain 3 moved the same
> way -- hole penalty up **100x**, line reward halved -- and fell from 34.57 to
> **11.46** points per piece, the worst collapse in that run and from the best
> opening function in it. Same direction, opposite outcome. So the direction is
> not what distinguished this chain, and the project has no account of what did
> beyond "how far"; it is listed as an open question in
> [the-best-powered-null-and-the-inert-revisions.md](the-best-powered-null-and-the-inert-revisions.md)
> §6, which a term-level replay over a grid of weights could answer without a
> model. One more reason the +8.64 here should not be read as the loop working.

> **Withdrawn 2026-11-24 (later the same day): this was not a reweighting.**
> The term-level replay ran. **Iteration 0's height and bumpiness terms were
> dead** — it scanned up from row 19 and stopped at the first filled cell, so
> every height was `19 - 19 = 0`, which §3 of this very document already
> recorded as `height: blind` and counted among its three repairs. Iteration 5
> fixed the scan. Crossing the repair against the reweighting:
>
> | | |
> |---|---:|
> | repair alone, weights unchanged | **+3.25** |
> | reweighting alone, heights still dead | **−3.90** |
> | both | +9.16 |
> | interaction | **+9.81** |
>
> **The new weights make the broken function worse.** They are worth +5.91 only
> once the terms they weight are alive. So this chain is a capability repair,
> which is the one thing the loop has been shown to do, and "the project's only
> clean example of a revision getting a weighting right" is withdrawn. This
> document counted the same event as a repair in §3 and credited it to
> reweighting here, and never connected the two.
>
> Worse for the baseline: **iteration 0's 41.55 was 63% tie-breaker.** With its
> trailing `unique_term` removed it scores **15.29**, because with dead height
> terms 55% of its decisions were ties at the maximum and that term — nominally
> worth at most 0.199 — was the policy. It prefers lower placements, and
> preferring low is worth +20.42 of the +26.26 it contributes. See
> [the-best-revision-was-a-repair.md](the-best-revision-was-a-repair.md).

### Chain 2: a sign flip, carried forward twice, 39.4 to 13.5

`tops[col]` is the row index of the topmost filled cell, and **row 0 is the
top**, so a *larger* `sum_tops` means a *lower* stack. Iteration 0 had the sign
right:

```python
# iteration 0 -> 39.4   (and iteration 2, still correct -> 36.3)
return lines * 50 + sum_tops - holes * 20 - unevenness * 10 - max_height * 3
# iteration 3 -> 32.2   one character different, and now it rewards building tall
return lines * 50 - sum_tops - holes * 20 - unevenness * 10 - max_height * 3
```

Iterations 4 and 5 kept the inverted sign and added weight to the terms around
it. The eval totals fall monotonically across the whole chain: **24,710 →
11,470 → 5,810 → 1,860 → 820**. Five revisions, every one worse than the last,
and the feedback at each step said the score had dropped.

### The same bug sits inside the second-best function

Chain 0's iteration 5 -- **47.01 points per piece**, the project's second-best
figure -- contains the identical inversion:

```python
score_val -= sum_top * 10.0        # sum_top is large for an empty board
```

An empty board scores −2,000 on this term and a board filled to the top scores
0. It is the same mistake that destroyed chain 2. It does no damage here only
because the terms around it are an order of magnitude larger: one line clear is
worth 3,000 and a deep hole 200, so the inverted term never decides a placement
that matters.

**So the inversion is not what separates the best chain from the worst.** What
separates them is whether the rest of the weighting drowns it -- which is a
property of the whole function, not of the edit the model made. That is the
credit-assignment problem in one example: the chain that broke itself was given
the same symptom table as the chain that fixed itself.

---

## 5. A failure class the repo did not have

Chain 2's iteration 1 produced no function at all:

| field | value |
|---|---|
| `played` | `false` |
| `tokens_out` | **14000** — exactly the configured `max_tokens` |
| `latency_seconds` | 701.1 |
| `invalid_outputs` | 1 |

The model was still writing when the budget ran out, so there was no complete
code block to extract. This is the project's **fifth rejected generation and the
first of its kind**: the other four were one syntax error and three `import
math` violations, all at iteration 0. This one is a **length cap at a revision
step**, which means
[the-import-rule-fails-three-times-in-five.md](the-import-rule-fails-three-times-in-five.md)
is counting one phenomenon where there are two.

**The lineage survived it.** `loop.py` keeps the last function that actually
played rather than carrying an empty source forward, so iteration 2 was built
from iteration 0's function and feedback -- confirmed by the two files sharing
their first fourteen lines. The log shows the position as a failure and the
chain continues, which is the designed behaviour and the right one: the
alternative sends the next prompt an empty code block while still numbering it
a continuation.

---

## 6. Two results worth separating from the null

**The project's best functions now rest on real play.** The README's caveat that
"the best chain's rate rests on about 1,000 pieces against the heuristic's
10,467" is out of date:

| position | rate | pieces | games censored by the budget |
|---|---:|---:|---:|
| chain 1, it5 | **50.19** | 18,164 | 8 of 10 |
| chain 0, it5 | **47.01** | 19,222 | 9 of 10 |

Both beat the hand-written heuristic's 43.5, with 0 sandbox failures, over
roughly **19,000 pieces each**. Seventeen of the run's 28 budget-censored games
belong to these two positions: these functions do not die, they run out of
budget. That is a stronger comparison than the project has had, and it is the
first time a model-written function has been censored at this rate.

**The dead-function proportion still does not move.** One revival, no deaths,
sign test p = 1.000. Pooled across all three loops: **78 transitions, 6
revivals, 5 deaths, p = 1.000.** Consistent with
[the-zeros-rate-does-not-move-either.md](the-zeros-rate-does-not-move-either.md),
and still far short of the 15–55 chains that test needs.

---

## 7. Cost

| | |
|---|---:|
| wall clock | 3 h 42 m |
| generations | 36 |
| latency per generation | mean 369.6 s, median 364.9 s, max 701.1 s |
| tokens | 51,769 in / 337,273 out |
| dollars | 0.00 (local) |

Of the 36 generations, 35 produced a function and 34 produced one that played.

---

## 8. Reproducing every number above

No model required; all of it is replay and arithmetic, a few seconds.

```bash
uv run python - <<'PY'
import json, collections, itertools, math, statistics
from tetris_bench.term_diagnostics import classify_directory

rows = [json.loads(l) for l in open("runs/published/30b-pilot/loop.jsonl")]
g = collections.defaultdict(lambda: [0, 0])
for r in rows:
    if r.get("split") == "eval":
        a = g[(r["chain"], r["iteration"])]
        a[0] += r["score"]; a[1] += r["pieces_placed"]
rate = {k: s / p for k, (s, p) in g.items() if p}

for c in range(6):
    its = sorted(i for (cc, i) in rate if cc == c)
    print("chain %d" % c, " ".join("%5.1f" % rate[(c, i)] for i in its),
          "gain %+.2f" % (rate[(c, 5)] - rate[(c, its[0])]))
gains = [rate[(c, 5)] - rate[(c, sorted(i for (cc, i) in rate if cc == c)[0])]
         for c in range(6)]
sd = statistics.stdev(gains)
it0 = [rate[(c, 0)] for c in range(6)]
print("median gain %+.2f  paired sd %.2f  MDE n=6 %.2f"
      % (statistics.median(gains), sd, 2.8 * sd / math.sqrt(6)))
print("cross-chain sd %.2f  ratio %.2f" % (statistics.stdev(it0), sd / statistics.stdev(it0)))
print("chains for +8.04: scaled %.0f, measured %.0f"
      % ((2.8 * 10.54 / 8.04) ** 2, (2.8 * sd / 8.04) ** 2))

# section 3: probes
by = {}
for v in classify_directory("runs/published/30b-pilot/functions"):
    ch = int(v.label.split("chain")[1].split("-")[0]); it = int(v.label.split("iter")[1])
    by[(ch, it)] = v.strategy_capable
print("probe-clean per iteration:",
      [sum(1 for c in range(6) if by.get((c, i))) for i in range(6)])
rep = sum(1 for c in range(6) for i in range(5)
          if (c, i) in by and (c, i + 1) in by and not by[(c, i)] and by[(c, i + 1)])
brk = sum(1 for c in range(6) for i in range(5)
          if (c, i) in by and (c, i + 1) in by and by[(c, i)] and not by[(c, i + 1)])
print("repairs %d  regressions %d" % (rep, brk))

clean = [gains[c] for c in (0, 2, 3)]; other = [gains[c] for c in (1, 4, 5)]
obs = statistics.fmean(clean) - statistics.fmean(other)
allv = clean + other
d = [statistics.fmean([allv[i] for i in s])
     - statistics.fmean([allv[i] for i in range(6) if i not in s])
     for s in itertools.combinations(range(6), 3)]
print("clean %+.2f vs other %+.2f  permutation p = %.3f"
      % (statistics.fmean(clean), statistics.fmean(other),
         sum(1 for x in d if abs(x) >= abs(obs)) / len(d)))

# section 5: the truncated generation
# one row per training seed, all three identical: the generation never played
bad = [r for r in rows if (r["chain"], r["iteration"]) == (2, 1)][0]
print("chain2 it1: played=%s tokens_out=%d latency=%.1f"
      % (bad["played"], bad["tokens_out"], bad["latency_seconds"]))

# section 6: censoring and cost
for key in ((1, 5), (0, 5)):
    ev = [r for r in rows if r.get("split") == "eval"
          and (r["chain"], r["iteration"]) == key]
    print("chain%d it%d: %.2f over %d pieces, %d censored" % (
        key[0], key[1], sum(x["score"] for x in ev) / sum(x["pieces_placed"] for x in ev),
        sum(x["pieces_placed"] for x in ev),
        sum(1 for x in ev if x["cause"] == "piece_limit")))
lat = [r["latency_seconds"] for r in rows if r.get("latency_seconds")]
print("36 generations, mean %.1fs, tokens %d/%d" % (
    statistics.fmean(lat), sum(r.get("tokens_in", 0) or 0 for r in rows),
    sum(r.get("tokens_out", 0) or 0 for r in rows)))
PY
```

The sign flip and the inversion inside the winner are visible directly:

```bash
tail -1 runs/published/30b-pilot/functions/qwen3-30b-chain2-iter2.py   # + sum_tops
tail -1 runs/published/30b-pilot/functions/qwen3-30b-chain2-iter3.py   # - sum_tops
grep -n "sum_top" runs/published/30b-pilot/functions/qwen3-30b-chain0-iter5.py
```

**Validity check.** Every σ here is a spread over generations, so it would be
wrong if two "independent" samples were the same function:

```bash
md5 -q runs/published/30b-pilot/functions/*.py | sort -u | wc -l   # 35 of 35
```

---

## 9. What this changes

1. **The 30B's published sample size is withdrawn.** 14–28 chains becomes **34**
   for a +8.04 target. The pilot was the right call and the figure it replaces
   was a guess wearing a decimal point.
2. **No borrowed σ_d, ever again.** Three rungs give 0.70x, 1.05x and 2.39x. A
   power claim in this project either measures its own paired term or says out
   loud that it is extrapolating.
3. **Refinement joins repair as untested-and-unpromising rather than untested.**
   The first rung with working functions to improve ended with the same number
   of working functions it started with.
4. **A rejection is two different events.** Rule violations and length-cap
   truncations are both "no function", and the import-rule denominator needs to
   say which it is counting.
5. **The piece-budget caveat relaxes.** The project's best functions are now
   measured over ~19,000 pieces, not ~1,000.

---

## 10. Open questions

1. **Is chain 1's reweighting reproducible, or is it this run's lucky chain?**
   One chain reaching 50.19 from 41.6 is the project's only clean example of
   outcome feedback producing a correct weighting change. At σ_d = 16.76 it is
   also entirely consistent with noise. Distinguishing them needs the 34 chains
   section 2 now asks for -- about 19.6 hours on this rung.
2. **Would a larger `max_tokens` remove the truncation class, or move it?** The
   cap is 14,000 across all rungs so the comparison stays fair, and one
   generation in 36 hit it. Raising it for one rung would break the comparison;
   raising it everywhere costs a re-run of the ladder.
3. **Does the loop ever repair a sign inversion?** Three are now on record --
   the 4B's `+ max_col_height * 30`, chain 2's `- sum_tops`, chain 0's
   `- sum_top` -- and none was fixed by a later revision, including the two that
   were visibly costing points. n=3 is not a rate, but it is the most specific
   bug class the corpus has.
