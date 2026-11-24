# The 30B loop is underpowered, not futile

**Date:** 2026-11-23 · **Model:** `qwen3:30b-a3b` (MoE, ~3B active)
**Unit:** points per piece (`eval_rate`), 2,000-piece budget
**Sources:** `runs/published/ladder/loop.jsonl` (iteration 0, 15 chains),
`runs/published/five-chain/loop.jsonl` (the 14B's 6-iteration loop)

**Status:** this document **overturns a claim made earlier in the project** —
that the 30B "cannot demonstrate improvement at any affordable sample size".
That claim does not survive re-derivation. The obstacle is real but it is a
different obstacle, and the practical advice changes as a result.

---

## 1. The claim that was wrong

The earlier reasoning was: the smallest gain detectable at five chains is
**19.0** points per piece, the 30B's remaining headroom is **17.5**, therefore
the experiment cannot succeed and should not be run.

Both numbers are correct. Neither supports the conclusion.

| quantity | value | what it is |
|---|---:|---|
| `2.8 × σ / √5`, σ = 15.134 | **18.95** | minimum detectable gain at n=5 |
| `43.5 − 25.98` | **17.52** | heuristic reference minus the 30B's median |

`2.8` is `z₀.₉₇₅ + z₀.₈₀` — 80% power, α = 0.05, two-sided.

The error is that **n=5 was treated as the affordable ceiling.** It is not. One
more chain clears the bar:

| chains | minimum detectable gain | clears 17.52? | 30B loop cost |
|---:|---:|---|---:|
| 5 | 18.95 | no | 2.9 h |
| **6** | **17.30** | **yes** | **3.5 h** |
| 10 | 13.40 | yes | 5.8 h |
| 18 | 9.99 | yes | 10.4 h |

The 30B is the **second-fastest rung in the project** at 346 s per generation —
behind the 4B's 297 s and ahead of the 8B's 557 s and the 14B's 832 s. MoE
makes it cheap. A six-chain, six-iteration 30B loop is three and a half hours.
Nothing here is unaffordable.

---

## 2. The real obstacle is effect size

The binding constraint is not how finely we can measure a gain. It is that
**the gain being hoped for is far larger than any the loop has ever produced.**

At the time of writing the project's only completed loop was the 14B
five-chain run; the 4B and the 30B have since run too, and neither changes the
figures in this section, which are the ones the 14B supported. Its first-to-last
gains, per chain, in points per piece:

| chain | 0 | 1 | 2 | 3 | 4 | median |
|---|---:|---:|---:|---:|---:|---:|
| gain | +8.04 | +0.31 | **−10.54** | +9.46 | +10.00 | **+8.04** |

Median curve: 12.55 → 20.58. The **largest gain any chain has ever achieved is
+10.00**, and one chain went backwards by 10.54.

Reaching parity with the hand-written heuristic from the 30B's median requires
**+17.52** — about **1.75× the best gain ever observed** and 2.2× the median.
So the earlier calculation was not describing an underpowered experiment; it was
describing an experiment aimed at an effect the mechanism has never produced.

### Powering for a realistic effect instead

Aim at the gain the loop actually delivers (+8.04) and the sample-size question
changes shape. Two estimates of the paired standard deviation σ_d, because the
honest answer is a range:

| σ_d estimate | basis | chains for +8.04 | 30B cost |
|---|---|---:|---:|
| **15.13** | cross-chain spread, used as a conservative proxy | 28 | 16.2 h |
| **10.54** | the 14B's *measured* paired σ_d (8.74), scaled by the two rungs' generation spread (15.13/12.55) | 14 | 8.1 h |

The second is the better estimate and the first is the safer one. The 14B's
measured paired σ_d is **8.74**, only 0.70× its cross-chain spread — iterations
within a chain share a lineage, so their differences vary less than two
independent generations do. Using cross-chain spread as σ_d therefore overstates
the requirement by roughly a factor of two in n.

> **Later correction (2026-11-23, same day): the 0.70 ratio is a property of the
> 14B, not of the method.** The 4B loop measured its own paired σ_d at **8.69**
> against a cross-chain spread of 3.63 — a ratio of **2.39×**, inverting the
> relationship this section assumes. On that rung a single revision can move a
> chain from 8.35 to 0.27 and back to 10.47, so iterations within a chain do not
> share a stable lineage at all. The "measured-scaled" column above is therefore
> the **optimistic end** of a range that can go the other way, and the 30B's
> 14-chain figure should be read as a lower bound until its paired σ_d is
> measured directly. The 6-chain pilot in [Open questions](#6-open-questions) is
> now the precondition for the larger run rather than a nice-to-have. See
> [4b-loop-reweights-a-crash-five-times.md](4b-loop-reweights-a-crash-five-times.md).

**So a properly aimed 30B loop needs 14–28 chains, or 8–16 hours.** Affordable,
substantial, and nothing like impossible.

> **Measured 2026-11-24, and this range was wrong.** The six-chain pilot ran and
> measured the 30B's paired σ_d directly: **16.76**, against the 10.54 scaled
> above and the 15.13 conservative proxy. The scaled figure was too low by
> **1.59×**, so the requirement for a +8.04 target is **34 chains, about 19.6
> hours** — outside the range this section gives, and above the conservative
> column it was meant to be bounded by. The ratio to cross-chain spread came out
> **1.05×** here, which with the 14B's 0.70× and the 4B's 2.39× makes three
> rungs and three ratios spanning 3.4×. **There is no constant to scale by**, so
> the method in this section is retired: a power claim measures its own paired
> term or says it is extrapolating. See
> [the-30b-ships-the-best-function-and-the-worst-collapse.md](the-30b-ships-the-best-function-and-the-worst-collapse.md).

---

## 3. Why the 8B is still the better first spend

The 30B being runnable does not make it the best use of the next overnight slot.
The comparison that matters is headroom against noise, not cost:

| rung | median | headroom to 43.5 | generation | n=10 detectable | headroom ÷ detectable | n=10 cost |
|---|---:|---:|---:|---:|---:|---:|
| `qwen3-8b` | 15.63 | **27.87** | 557 s | 12.16 | **2.29** | 9.3 h |
| `qwen3-30b` | 25.98 | 17.52 | 346 s | 13.40 | 1.31 | 5.8 h |

The 30B loop is the *cheaper* run — 5.8 h against 9.3 h — but the 8B has 59%
more room to move against a slightly smaller noise term, giving it a
headroom-to-noise ratio of 2.29 against the 30B's 1.31. The 8B is the better
experiment because it has more space for a result to appear in, not because the
30B is barred.

**Recommended next run: the 8B loop, 10 chains, 6 iterations, ~9.3 hours.**

---

## 4. What this changes

1. **The futility claim is withdrawn.** A 30B loop is a legitimate experiment at
   6 chains (3.5 h) for a heuristic-parity-sized effect, or 14–28 chains
   (8–16 h) for a realistically-sized one.
2. **Any future power claim must state its σ_d and its target effect.** The
   earlier error came from pairing a cross-chain σ with an aspirational effect
   size and never naming either. Both belong in the sentence.
3. **`headroom` needs its ceiling named.** 17.52 is the distance to *parity with
   the hand-written heuristic*, which is a reference point and not a hard
   ceiling — the 30B's own best chain scored **46.36**, above the heuristic's
   43.5. Measuring headroom from the median to the best demonstrated chain gives
   20.38 instead, which *is* detectable at n=5. The two candidate ceilings are
   2.86 points apart and the n=5 bar of 18.95 falls between them, so the
   feasibility verdict for this rung is decided entirely by which ceiling you
   name -- which is itself the reason not to report it as a one-liner.
4. **The median is the right floor.** Headroom is measured from the median across
   chains (25.98), not the best chain (46.36), because `curves.py` reads the
   curve from the median — best-of-n rises about 97% under pure noise.

---

## 5. Reproducing every number above

No model required; all of it is replay and arithmetic, sub-second.

```bash
uv run python - <<'PY'
import json, math, statistics
from tetris_bench.curves import build_curves

lad = [json.loads(l) for l in open("runs/published/ladder/loop.jsonl")]
for c in build_curves(lad):
    r = [p.headline for p in c.positions]
    print("%-11s median %6.2f  best %6.2f  gen-sd %6.2f" % (
        c.model, statistics.median(r), max(r), c.chain_spread()))
    L = [x["latency_seconds"] for x in lad
         if x["model"] == c.model and x.get("latency_seconds")]
    print("            generation mean %.1fs" % statistics.fmean(L))

(f,) = build_curves([json.loads(l) for l in open(
    "runs/published/five-chain/loop.jsonl")])
d = [f.chain_series(ch)[-1].headline - f.chain_series(ch)[0].headline
     for ch in f.chains]
print("14B gains", [round(x, 2) for x in d],
      "median %.2f  paired sd %.2f  cross-chain sd %.2f"
      % (statistics.median(d), statistics.stdev(d), f.chain_spread()))

mde = lambda s, n: 2.8 * s / math.sqrt(n)          # 80% power, alpha=.05
need = lambda s, e: (2.8 * s / e) ** 2
print("30B MDE n=5 %.2f  n=6 %.2f" % (mde(15.134, 5), mde(15.134, 6)))
print("headroom to heuristic %.2f" % (43.5 - 25.98))
print("chains for +8.04: conservative %.1f, measured-scaled %.1f"
      % (need(15.134, 8.04), need(8.74 * 15.134 / 12.55, 8.04)))
PY
```

**Validity check on the samples themselves.** Every σ here is a spread over
generations, so it would be wrong if any two "independent" samples were in fact
the same function — the failure mode just found in
[`counterexample_arm.py`](counterexample-is-the-sampler-not-the-board.md), where
consecutive run indices produced byte-identical output. Neither source used here
has it:

```bash
md5 -q runs/published/ladder/functions/qwen3-30b*.py | sort -u | wc -l   # 15 of 15
md5 -q runs/published/five-chain/functions/*.py      | sort -u | wc -l   # 33 of 33
```

All 60 ladder functions and all 33 five-chain functions are distinct, so the
chain counts these calculations rest on are real.

---

## 6. Open questions

1. ~~**σ_d has never been measured on the 30B**, only scaled from the 14B. The
   first six chains of any 30B loop would measure it directly, which is an
   argument for running the cheap 6-chain version as a pilot before committing
   to 14–28.~~
   **Closed 2026-11-24: the pilot ran and the scaling was wrong.** Measured
   σ_d is **16.76** against the 10.54 scaled here, so the requirement is **34
   chains** rather than 14–28. The pilot also produced the project's best
   function (50.19 points per piece at iteration 5) and a chain that declined at
   all five revisions, with the same sign inversion present in both. See
   [the-30b-ships-the-best-function-and-the-worst-collapse.md](the-30b-ships-the-best-function-and-the-worst-collapse.md).
2. **Is +8 the ceiling on loop gains, or the ceiling on the 14B's gains?**
   **Partly answered, and not reassuringly.** The 4B loop produced a median
   change of **−3.77** against a minimum detectable change of 10.88, so it shows
   no gain rather than a smaller one. One rung with a gain and one rung with
   nothing measurable does not establish a ceiling; it establishes that the
   14B's +8 is not a general figure. The 8B still turns this into a measurement.
3. ~~**Three of the 30B's 15 chains scored 0.0.** If the loop's main value on
   this rung is rescuing dead functions rather than improving live ones, the
   relevant effect is a change in the *rate of zeros*, which is a proportion
   test and a completely different power calculation from the one above.~~
   **Tested and null, with the power calculation done.** Across both completed
   loops: 5 revivals against 5 deaths over 50 transitions, sign test p = 1.000.
   The proportion test needs **15-55 chains** depending on effect size, against
   the 5 that ran — so this was undetectable by design rather than untested. See
   [the-zeros-rate-does-not-move-either.md](the-zeros-rate-does-not-move-either.md).
