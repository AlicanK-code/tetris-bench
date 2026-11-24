# The zeros rate does not move either

**Date:** 2026-11-23 · **Models:** `qwen3:4b`, `qwen3:14b` · no GPU, pure replay
**Sources:** [`runs/published/4b-loop/`](../../runs/published/4b-loop/),
[`runs/published/five-chain/`](../../runs/published/five-chain/)
**Code:** `src/tetris_bench/zeros_rate.py` (pure, unit-tested),
`analysis/zeros_rate.py` (presentation)

Four earlier write-ups raised the same suspicion and none tested it: if the
loop's value is **rescuing functions that score nothing** rather than improving
ones that work, the effect is a change in a *proportion*, and comparing medians
cannot see it. `curves.py` compares medians.

It is now tested. The proportion does not move, and the more useful result is
**why nobody could have settled this with any run this project has done** — it
needs 15 to 55 chains, where the loops ran 5.

---

## 1. Defining "dead" without picking a round number

Exactly 0.0 is too strict: a function whose every call crashes still accrues a
little score from the fallback placement, so it lands near zero rather than at
it. "Under 1.0" is arbitrary.

The line used here is measured. Random play on the evaluation split (seeds
1000-1009, 2,000-piece budget, 20 agent seeds) averages **0.327** points per
piece, and a *single 10-game evaluation* of it — the same evaluation a loop
position gets — ranges 0.000 to 1.163 with a **95th percentile of 0.851**.

So **dead means at or below 0.851 points per piece**: inside the range random
reaches by chance on the same number of games. That is a measurement, not a
judgement, and `RANDOM_CEILING` carries the derivation in its docstring.

```bash
uv run python analysis/zeros_rate.py --measure-floor
```

---

## 2. The proportion does not move

```
4B    chain 0:  . . . . . .          14B   chain 0:  . . . . . .
      chain 1:  D . . . . .                chain 1:  D D D D D D
      chain 2:  . . . . . D                chain 2:  . . . . . .
      chain 3:  . D D D D D                chain 3:  . . . . . .
      chain 4:  . D . . D .                chain 4:  D . . D . .
```

| | it0 | it1 | it2 | it3 | it4 | it5 |
|---|---:|---:|---:|---:|---:|---:|
| 4B dead | 1/5 | 2/5 | 1/5 | 1/5 | 2/5 | 2/5 |
| 14B dead | 2/5 | 1/5 | 1/5 | 2/5 | 1/5 | 1/5 |

**Pooled first to last: 3 of 10 dead at iteration 0, 3 of 10 at iteration 5.**
Two chains revived, two died.

**Pooled across all 50 adjacent transitions: 5 revivals, 5 deaths.** A two-sided
exact sign test on the 10 discordant pairs gives **p = 1.000** — the most
perfectly null result in the project.

> **Added 2026-11-24.** The 30B pilot contributes 28 more transitions and does
> not disturb it: **1 revival, 0 deaths**, one chain dead at iteration 0 and
> none at iteration 5. Pooled over all three loops: **78 transitions, 6
> revivals, 5 deaths, p = 1.000.** Still far short of the 15–55 chains §3 asks
> for.

> **Added 2026-11-24 (later the same day).** The 8B loop adds the largest
> contribution any single run will make here -- ten chains on the rung with the
> most dead functions, **7 revivals against 5 deaths**, with 4 of 10 dead at
> iteration 0 and 2 of 10 at iteration 5. Pooled over all four loops: **130
> transitions, 14 revivals, 11 deaths, p = 0.690.** That is now within reach of
> §3's requirement rather than far short of it, and the answer has not changed.
> One caveat specific to the 8B: its chain 4 sits at 0.44–1.61 points per piece
> against a `RANDOM_CEILING` of 0.851, so it crosses the dead line three times
> without its behaviour changing; without that chain the pooled count reads 13
> against 10. See
> [the-best-powered-null-and-the-inert-revisions.md](the-best-powered-null-and-the-inert-revisions.md).

Two details worth keeping:

- **The test is paired, deliberately.** Each iteration is compared against *its
  own* previous iteration, and the evidence is only the pairs that changed
  state. An unpaired proportion test would treat 10 positions from 2 runs as 10
  independent draws and overstate its confidence.
- **p = 1.0 is not evidence of no effect.** With 10 discordant pairs split 5-5
  it is the absence of evidence either way, which is why §3 exists.

---

## 3. Why no run here could have answered it

This is the part worth taking away. **Power is spent on discordant pairs, not on
chains**, and only **10 of 50** pairs changed state at all — a 20% discordance
rate. A six-iteration chain contributes five pairs, so the sample size in chains
is:

| if revivals are … of changed pairs | chains needed | 4B | 30B | 8B | 14B |
|---|---:|---:|---:|---:|---:|
| 90% (a strong rescue effect) | **15** | 7.4 h | 8.7 h | 13.9 h | 20.8 h |
| 80% | **25** | 12.4 h | 14.4 h | 23.2 h | 34.7 h |
| 70% (a modest one) | **55** | 27.2 h | 31.7 h | 51.0 h | 76.3 h |

80% power, α = 0.05 two-sided, by simulation rather than a normal approximation,
because the test is exact and discrete and an approximation is wrong at these
sizes *in the direction that flatters the experiment*.

Both completed loops ran **5 chains**. Even the most generous alternative needs
three times that. So the honest reading of the four earlier write-ups is not
"nobody got round to it" but **"the design could not have detected it"** — and
the cheapest version is a 15-chain 4B loop at 7.4 hours, which is in the same
range as the 8B run already recommended for the *mean*.

---

## 4. What the two near-misses actually were

Neither chain that changed state did so for a reason that looks like learning.

- **4B chain 3** went dead at iteration 1 and stayed dead for five iterations,
  because its revision wrote `total_empty = total_empty(board)` and crashed on
  every call. The revise prompt quoted the `UnboundLocalError` back to it each
  time. That is one "death" in this table and
  [a whole write-up](4b-loop-reweights-a-crash-five-times.md) on its own.
- **14B chain 4** was dead at iteration 0, alive at 1, dead again at 3, alive at
  4. Three state changes in six iterations on one chain, which is the volatility
  that makes a 20% pair-discordance rate and no signal.

**14B chain 1 was dead at all six iterations** and 4B chain 0 alive at all six.
The loop neither rescued the one nor spoiled the other.

---

## 5. What this closes

**Closes:** the open question carried by
[the ladder](size-ladder-is-a-step.md),
[the 30B power analysis](30b-loop-is-underpowered-not-futile.md),
[the 4B loop](4b-loop-reweights-a-crash-five-times.md) and
[the capability probe](the-loop-does-not-repair-capability.md). The rate of dead
functions is unchanged by the loop on the available data, and the sample size
needed to say more is now a number rather than a shrug.

**Does not close:** whether a 15-chain run would find something. It might; this
says only that 5 chains cannot. Note also that both loops are rungs where dead
functions are common to begin with — a rung that starts mostly alive measures
something else again, as with the capability probes.

**Three ways the loop could have been doing something invisible to the curve
have now been checked**: the mean (no), function-level capability (no), and the
dead-function proportion (no, and underpowered). They agree.

---

## 6. Reproducing it

```bash
uv run python analysis/zeros_rate.py                  # the whole table, ~1s
uv run python analysis/zeros_rate.py --measure-floor  # re-derive the 0.851 line
uv run pytest tests/test_zeros_rate.py                # 23 tests on the arithmetic
```
