# Results in full

Every figure here is read from **held-out** seeds whose outcomes the model never
saw. This is the long form; the [README](../README.md) carries the summary, and
each result links to its own write-up in [`findings/`](findings/) and its
artifacts in [`runs/published/`](../runs/published/).

Moved out of the README on 2026-11-25, unchanged apart from this header.

**The comparator.** A model result is compared against the hand-written 1-ply
heuristic at **43.34 points per piece** — its rate on the same ten held-out
sequences at the same 2,000-piece budget that every model figure uses. Random
play under those conditions is **0.33**. Both come from
[`baselines.py`](../src/tetris_bench/baselines.py), which also records why the
heuristic reads 43.16 on twenty sequences and 43.46 run to exhaustion: the rate
is stable to about 0.3, not to the decimal, and older passages below quote
whichever figure was in use at the time. Where one of them is used as a
comparator it now carries its conditions.

---

## Results

Every figure below is read from **held-out** seeds whose outcomes the model never
saw, at zero dollars.

**The headline measure is points per piece, not total score.** A total is
censored by the piece budget -- a game that hits the cap is cut off rather than
finished, so its score is a lower bound, and the best function here was censored
in 8 of 10 games. A rate does not have that failure mode and is empirically
budget-independent: the hand-written heuristic measures 43.16-43.46 points per
piece at 500, 2,000, 20,000 and 50,000 pieces alike, and **43.34** under the
conditions the models are measured in. Totals are still reported
beside it, because survival is a separate thing worth knowing. Rates are totals
over totals across a position's ten unseen sequences, which is what the
baseline's own rate is — 454,900 / 10,467 run to exhaustion, or 84,720 / 1,955
on the ten evaluation sequences at the default budget.

### The curves

One figure per rung, each drawn from the published log. The per-chain lines are
the point: chains are independent lineages that never see each other's
functions, so a rising median over three agreeing chains is a result and the
same median over one chain carrying two collapsed ones is not. The wide band is
the bar a change must clear; the narrow one is seed noise alone. A red cross is
a generation the validator rejected.

| rung | figure |
|---|---|
| `qwen3-4b`, 5 chains | [curve-qwen3-4b.png](../runs/published/figures/curve-qwen3-4b.png) |
| `qwen3-8b`, 10 chains | [curve-qwen3-8b.png](../runs/published/figures/curve-qwen3-8b.png) |
| `qwen3-14b`, 5 chains | [curve-qwen3-14b.png](../runs/published/figures/curve-qwen3-14b.png) |
| `qwen3-30b`, 6 chains | [curve-qwen3-30b.png](../runs/published/figures/curve-qwen3-30b.png) |

![The 8B's curve: ten chains, six iterations, held-out points per piece and
pieces placed](../runs/published/figures/curve-qwen3-8b.png)

**These figures and the tables below use different conventions, deliberately,
and the numbers differ because of it.** The figures are drawn by
`analysis/plots.py` from `Curve`, which scores a rejected generation as a real
zero and reports the **gain of the medians**; the tables exclude rejected
positions and report the **median of the per-chain gains**. On the 8B that is
8.3 → 17.0 against 15.63 → 17.04, and on the 30B it is −5 against +7.37. Both
are defensible -- a rejection genuinely produced no function, and it genuinely
is not a measurement of a function -- and neither is the other's error. The
per-rung writeups in [`runs/published/`](../runs/published/) say which each uses.

```bash
uv run python analysis/plots.py --log runs/published/8b-loop/loop.jsonl
```

The honest summary of what this benchmark has measured so far: **the clearest
signal is whether a model can express a strategy at all, and the improvement
curve is the noisier of the two stories.** That is not the result the project set
out to find, so the sections below are ordered by how well the evidence holds up
rather than by how interesting the claim sounds.

### Most model-written scorers are broken, not bad

A score alone cannot tell a weak strategy from arithmetic that is structurally
incapable of being one. Both produce a low number. So each generated function is
run against four probes -- pairs of boards whose ranking is not a matter of
opinion, like a 3-deep stack against a 12-deep one -- and a function is
**strategy-capable** only if it gets all four right.

| rung | strategy-capable |
|---|---:|
| `qwen3-4b` | 4/15 |
| `qwen3-8b` | 5/15 |
| `qwen3-14b` | 3/15 |
| `qwen3-30b-a3b` | **11/15** |

Across 60 first attempts, **23 were capable and 37 were not**. On the 14B's
six-iteration sweep the rate is 7 of 33 functions (21%).

This is not a quibble about code quality; it changes what a score means. Pooled
across all four rungs, probe-clean functions reach a held-out median of **26.9
points per piece** against **1.2** for probe-broken ones (Mann-Whitney
p = 0.000001).

```bash
uv run python analysis/term_diagnostics.py runs/published/ladder/functions --flip
```

**Every defect is board geometry.** Of the 56 functions that loaded, **all 56
read `lines_cleared` correctly** -- the one quantity specific to this harness,
which arrives in the placement dict rather than being derived from the board.
The failures are height (26/56), holes (20/56) and blindness above the first gap
(16/56), and they share one cause: the board has row 0 at the top, and models
repeatedly write code assuming it is the floor. The benchmark's own conventions
are not the difficulty; the spatial reasoning is.

Nothing from these probes is fed back to a model. Telling it that its height term
is dead would hand it the diagnosis, and self-diagnosis is the ability being
measured.

### The ladder is a step, not a slope

Four rungs, same prompt, 15 independent chains each, no feedback -- what each
model writes cold. The prompt was **byte-identical across all 60 generations**,
so the only variable is the model.

| rung | strategy-capable | median pts/piece | best pts/piece | median total | best total |
|---|---:|---:|---:|---:|---:|
| `qwen3-4b` | 4/15 | 7.4 | 15.6 | 290 | 880 |
| `qwen3-8b` | 5/15 | 15.6 | 35.1 | 880 | 5,940 |
| `qwen3-14b` | 3/15 | **1.9** | 39.0 | 40 | 9,820 |
| `qwen3-30b-a3b` | 11/15 | **26.0** | **46.4** | 2,580 | 81,300 |
| *hand-written heuristic* | — | *43.34* | *43.34* | *84,720* | *84,720* |

Medians are over all **15** positions per rung, with a rejected function counting
as a zero -- it failed, which is a result rather than missing data, and it is the
convention `analysis/curves.py` uses. That matters for the 8B and 14B, the two
rungs that had rejections: excluding them would raise the 14B's median from 1.9
to 12.5 and flatter exactly the rungs that failed.

The three dense rungs are **statistically indistinguishable from one another**
(every pairwise Fisher p >= 0.68, and the 14B sits *below* both smaller models).
The 30B separates: p = 0.002 against the three pooled. A trend test over
`log2(params)` returns p = 0.018, but it assumes a monotonicity the 8B-vs-14B
inversion violates, so [the write-up records it as not
quotable](findings/size-ladder-is-a-step.md).

**The step is also the only MoE on the ladder**, so size and architecture are
perfectly confounded here while three observations of dense scaling show no
effect at all. The supportable claim is therefore narrower than "capability
scales with size": dense Qwen3 from 4B to 14B is flat on this task, and a
30B-a3b is decisively better. Separating the two would need a dense model at or
above 30B, which does not fit in 32GB usefully -- so this stays a stated
confound rather than a loose end.

### The probes only predict a score from the 8B up

| rung | probe-clean median | probe-broken median | ratio |
|---|---:|---:|---:|
| `qwen3-4b` | 7.1 | 7.5 | **0.9x** |
| `qwen3-8b` | 31.4 | 0.5 | 63x |
| `qwen3-14b` | 24.9 | 0.4 | 62x |
| `qwen3-30b-a3b` | 33.5 | 0.0 | infinite |

In points per piece, like every other figure here.

**On the 4B, writing valid code buys nothing.** Its four clean functions score
the same as its eleven broken ones, because it then picks the wrong terms and
weights them incoherently -- one values a line clear at 10 against a row of
height at 5; another weights holes at 1 against max-height at 50, so it buries
holes to stay flat. Neither carries a bumpiness term, and both define a hole as a
cell walled on all four sides, which misses nearly every real one.

So the 4B fails at two levels and the probes see only the first. That is the
intended behaviour -- they test construct validity, not skill -- and it makes the
4B the wrong rung for loop experiments, since no feedback derived from its score
can steer it.

### The top rung matches a hand-written heuristic cold

Two `qwen3-30b-a3b` chains, both first attempts with no feedback, and which one
looks best depends entirely on the measure:

| | pts/piece | total | mean pieces | censored |
|---|---:|---:|---:|---:|
| chain 4 | **46.4** | 47,930 | 1,034 | 1/10 |
| chain 3 | 43.4 | **81,300** | 1,875 | 8/10 |
| *heuristic (Lee 2013), 10 eval seeds, 2,000 pieces* | *43.34* | *84,720* | *1,955* | *8/10* |

**Chain 3 wins on totals by surviving longer; chain 4 actually scores faster.**
That inversion is the switch to a rate earning its keep. Chain 3's 81,300 was a
lower bound -- censored in 8 of 10 games -- so the old headline was partly
reporting the budget. Chain 4 is censored once in ten, which makes its 46.4 the
more trustworthy figure of the two.

So the result is that a 4-bit local model, on its first attempt, **matches the
scoring rate of a tuned hand-written heuristic** -- 46.4 and 43.4 against
43.34.
Read that as parity rather than a win: the heuristic's rate is measured over
10,467 pieces and chain 4's over about 1,034, and a rate measured over a shorter
run has had less chance to meet the board states that punish a weak evaluator.

> **Update 2026-11-24.** The short-run caveat no longer applies to the project's
> best figures. Two functions from
> [the 30B pilot](#the-30b-ships-the-best-function-and-the-worst-collapse) score
> **50.19 and 47.01 over roughly 19,000 held-out pieces each**, censored by the
> piece budget in 8 and 9 games of 10. They do not die; they run out of budget.

Chain 4's function is 22 lines of lines, holes and bumpiness with **no height
term at all**. One chain in fifteen reproduced a Dellacherie-style evaluator
cold.

It stayed an awkward result for this project while it was the best one: a
first attempt, no loop involved. The 30B pilot has since produced two better
functions, both at iteration 5 -- which replaces the awkwardness rather than
removing it, because the gains that got there are smaller than the run's own
noise.

### The improvement curve is smaller than its own noise

Five independent chains, six iterations, the 14B. Each chain revises only its own
function and never sees another's, so a rising median cannot be selection bias.

| iteration | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---:|---:|---:|---:|---:|---:|
| median pts/piece | 12.5 | **21.4** | 18.0 | 18.1 | 16.0 | 20.6 |
| median total | 670 | 1,410 | 1,120 | 1,140 | 930 | 1,410 |

Paired against its own iteration 0 on identical seeds, chain by chain:

| chain | pts/piece | delta | t | delta as a total |
|---|---:|---:|---:|---:|
| 0 | 12.5 → 20.6 | +8.0 | 1.37 | +740 |
| 1 | 0.5 → 0.8 | +0.3 | 0.45 | +10 |
| 2 | 35.4 → 24.8 | **-10.5** | **-4.68** | -7,150 |
| 3 | 15.4 → 24.8 | +9.5 | 1.96 | +1,160 |
| 4 | 0.0 → 10.0 | **+10.0** | **4.75** | +460 |

**Three chains rose, one fell, and under a rate the rises and the fall are
comparable in size.** That is a change from the old headline, where chain 4's
repair (+460) looked trivial beside chain 2's collapse (-7,150) -- a 15x gap that
was mostly score growing superlinearly with survival. Per piece they are +10.0
and -10.5, and both are *more* significant than they looked.

Chain 4 rose from zero by deleting two inverted terms -- repair, not refinement.
Chain 2 fell by *adding* a term blind above the first gap, confirmed by execution
rather than inferred: a 3-cell column and a 9-cell column ten rows tall both
score -6 under its function. It was not censored at either end, so that
regression is real and not a budget artefact.

And the movement still sits inside the noise. Those five iteration-0 chains are
five samples of **one identical prompt**, and they scored 12.5, 0.5, 35.4, 15.4
and 0.0 points per piece -- a spread the tooling measures at **14.4**, against a
largest median movement of 8.9. `curves.py` reaches the same verdict by its own
route: *"gain +8, only 0.6x the noise bar of 13"*, and it puts the plateau at
iteration 0.

So the defensible claim is narrow: **the loop repairs broken scorers and does not
measurably improve working ones.** Whole sweep: 30 generations, 194,492 output
tokens, 5.67 hours, **$0**.

### The strongest result is a credit-assignment failure

From an earlier single-chain run of the 14B, published at
[`runs/published/clean-6iter/`](../runs/published/clean-6iter/) -- a different run
from the five-chain sweep above. Verified by replaying the saved functions, not
inferred from the scores. **Scores here are replays at the current 2,000-piece
budget**, which is why they exceed the figures in that run's own log: it was
played at the old 500-piece cap, where iteration 4 reads 14,860 over 378 pieces
and is censored in 5 of its 10 games.

1. Iteration 3 measured column height as a **row index** on a board whose row 0
   is the top, then subtracted it -- rewarding tall stacks. Score 470.
2. Iteration 4 flipped those signs to plus. Behaviourally correct, and it
   worked: 25,180. But the definition was still wrong; only the sign was fixed.
3. Iteration 5 corrected the *definition* instead, counting filled cells
   downward from row 0 with a `break`. On any board with an empty top row that
   returns 0 for every column, zeroing three of five terms. Score 6,850, and it
   blocked out on all ten seeds.

So the model fixed its bug by accident and then broke it again by correcting the
accident. Given only outcome feedback it never located the actual defect, and
that is the ability this benchmark set out to measure.

### Rate versus survival

That same iteration-4 function against the hand-written heuristic, both replayed
to exhaustion at a 50,000-piece budget so neither figure is censored. The model
function is measured on seeds 1000-1009 and the heuristic on 1000-1019, so the
seed sets overlap rather than match; on the same 20 seeds the model function
gives 24,060 over 602 pieces, which does not change the conclusion.

| | points/piece | pieces survived |
|---|---:|---:|
| heuristic (Lee 2013), run to exhaustion | 43.46 | 10,467 |
| 14B, iteration 4 | 40.2 | 626 |

**About 92% of the heuristic's scoring rate, and 6% of its survival.** The model
learned to clear lines about as efficiently as a tuned hand-written heuristic
and never learned to stay alive. Quoting totals alone would have called this
"69% of the heuristic" and hidden both halves -- see
[Reference baselines](design.md#reference-baselines).

This was the observation that eventually moved the headline onto a rate. It is
no longer the best rate in the project -- the 30B's 46.4 is -- but it is still
the clearest demonstration of *why* the two have to be reported separately.

```bash
uv run python analysis/baseline_ceiling.py --max-pieces 50000 --seeds 20
```

### The discriminate warning does not fix inert arithmetic

`strategy_v2` added a bolded warning that a function **must give different
candidates different scores**, with an actionable second half -- "check that each
term you use actually *varies*". Did it work?

**The comparison the question wanted is not available.** Of 134 published
generations, **132 received the warning and 2 did not**, and the two are one
model at one seed from the original prompt-comparison arm. That cannot be a rate.

What is measurable is whether inert functions persist *under* the warning.
Replaying every published function in the sandbox against eight boards:

| rung | ran | constant on **every** board |
|---|---:|---:|
| `qwen3-4b` | 43 | **5** |
| `qwen3-8b` | 13 | 0 |
| `qwen3-14b` | 54 | 0 |
| `qwen3-30b` | 15 | **0** |

**Five of 125 functions are inert on every board, all of them 4B, and three were
written under the warning.** In the single controlled v1/v2 pair that exists,
*both* members are inert -- so the one piece of direct evidence points at no
effect. The 30B is the only rung with no flatness anywhere.

**The transferable part is a measurement trap.** A naive probe -- "does it return
the same number for every candidate on a board?" -- over-reports by about five
times, because on a near-empty board many placements are genuinely equivalent
and a *correct* function scores them identically. On one empty board 29% of
functions look inert; on the mid-depth boards it is 5-6%. Only "constant on
every board" is a defect. Relatedly, `flat_moves` in the run records cannot
answer this at all: it counts a crashing function as flat, because the sandbox
returns `-inf` for a failed call.

Full write-up:
[docs/findings/the-discriminate-warning-does-not-fix-inert-arithmetic.md](findings/the-discriminate-warning-does-not-fix-inert-arithmetic.md).

### The import rule fails two times in five

> **Updated 2026-11-24.** On a 227-generation corpus the rate is **8 of 19
> (42%)**, and the "revisions never do it" paragraph below is **overturned**:
> the 8B loop produced four import rejections at revision steps. The numbers
> that follow are the 2026-11-23 figures, kept for the reasoning; the
> paragraph at the end of this section carries the current ones.

The ladder noted that three of the project's four rejections were `import math`
against a prompt that forbids imports in bold. Quantified, **the denominator is
the result.**

As "3 of 60 ladder generations" this is a 5% nuisance. But 55 of those 60 never
wanted `math` at all, so they had no occasion to obey the rule. **Five functions
in the whole 131-generation corpus reach for `math`. All five want `math.sqrt`.
Three of the five added the forbidden import and were rejected.**

| function | outcome |
|---|---|
| `qwen3-4b-chain1-iter0` | used `math.sqrt` correctly, no import |
| `qwen3-8b-chain5-iter0` | used `math.sqrt` correctly, no import |
| `qwen3-8b-chain7-iter0` | **imported -- rejected** |
| `qwen3-14b-chain9-iter0` | **imported -- rejected** |
| `qwen3-14b-chain14-iter0` | **imported -- rejected** |

The prompt did not withhold anything. Verified against the generation record
rather than the template, what was sent is bolded, names the substitute, and
gives the worked example:

> - **No imports.** `math` is already available as a name - use `math.sqrt(...)`
>   directly, with no import statement.

`math.sqrt` is the call in the example and the only `math` call any of the three
makes. The two successes matter as much: they show the instruction is followable
and the pre-injected `math` works, so the failures are not a broken facility or
impossible wording.

Cost: 3 generations, 27,743 output tokens, 38.6 minutes, producing nothing.

**Revisions do it too, at a rate not distinguishable from iteration 0's.** That
is the 2026-11-24 correction, and it is the same lesson one level deeper. The
original claim was "revisions never do it -- 0 of 55", reasoning that a revision
has the previous import-free function to copy where iteration 0 has only prose.
But all five occasions known then fell at iteration 0, so the revise condition
had never been tested: the zero was a *no occasion*. With the 8B loop's eight
occasions added, iteration 0 stands at **4 of 7 (57%)** and revisions at **4 of
12 (33%)**, Fisher's exact **p = 0.377**.

What survived is narrower and sharper. **No revision written immediately after a
rejection imported -- 0 of 5 -- against 4 of the other 45.** One 8B chain
imported at iterations 0, 2 and 4, was told each time in the validator's own
words, and complied at 1 and 5: the error message works while it is in the
context window and not one step beyond. At 0 of 5 that is an observation, not a
rate.

Full write-up:
[docs/findings/the-import-rule-fails-three-times-in-five.md](findings/the-import-rule-fails-three-times-in-five.md).

### The zeros rate does not move either

The last way the loop could have been doing something the curve cannot see. If
its value were **rescuing functions that score nothing** rather than improving
ones that work, the effect would be a change in a proportion, and comparing
medians would miss it entirely.

"Dead" is drawn at a measured line rather than a round number: random play
averages 0.327 points per piece on the evaluation split, and a single 10-game
evaluation of it -- the same evaluation a loop position gets -- reaches **0.851**
at the 95th percentile. At or below that is inside the range random hits by
chance.

| | it0 | it1 | it2 | it3 | it4 | it5 |
|---|---:|---:|---:|---:|---:|---:|
| 4B dead | 1/5 | 2/5 | 1/5 | 1/5 | 2/5 | 2/5 |
| 14B dead | 2/5 | 1/5 | 1/5 | 2/5 | 1/5 | 1/5 |

Pooled, **3 of 10 dead at iteration 0 and 3 of 10 at iteration 5**. Across all
50 adjacent transitions: **5 revivals, 5 deaths**, a paired exact sign test on
the 10 discordant pairs giving **p = 1.000**.

**The more useful result is that no run here could have settled it.** Power is
spent on pairs that *change state*, and only 10 of 50 did. At that 20% rate the
sample size is **15 chains** if revivals are 90% of changed pairs, **25** at 80%,
**55** at 70% -- against the 5 chains both loops ran. So the four earlier
write-ups that deferred this question were not negligent; the design could not
have detected it. The cheapest sufficient version is a 15-chain 4B loop at 7.4
hours.

The 30B pilot adds 28 transitions and does not move it: **1 revival, no deaths**.
The 8B loop then added the largest single contribution this question will get --
ten chains on the rung with the most dead functions, **7 revivals against 5
deaths**, 4 of 10 dead at iteration 0 and 2 of 10 at iteration 5. Pooled across
all four loops, **130 transitions, 14 revivals, 11 deaths, p = 0.690** -- now
within reach of the sample size asked for above rather than far short of it, and
the answer has not changed.

Full write-up:
[docs/findings/the-zeros-rate-does-not-move-either.md](findings/the-zeros-rate-does-not-move-either.md).

```bash
uv run python analysis/zeros_rate.py
```

### The loop does not repair capability either

If the loop were quietly fixing *broken* functions without moving *scores*, that
would be a real effect the curve cannot see -- and the last remaining way the
findings above could be understating it. All four loops can now be probed, and
it is not happening.

A function is **strategy-capable** when it answers all four probes correctly.
The fraction, by iteration:

| loop | it0 | it1 | it2 | it3 | it4 | it5 |
|---|---:|---:|---:|---:|---:|---:|
| **4B**, 5 chains | 1/5 | 1/5 | 1/5 | 1/5 | 1/5 | 1/5 |
| **14B**, 5 chains | 2/5 | 2/5 | 0/5 | 0/5 | 1/5 | 1/5 |
| **30B**, 6 chains | 4/6 | 4/5 | 6/6 | 4/6 | 5/6 | 4/6 |
| **8B**, 10 chains | 3/10 | 2/10 | 3/10 | 4/10 | 5/10 | 5/10 |

Pooled over the two five-chain loops, iteration 0 was **3 of 10** and iteration
5 was **2 of 10**: **1 repair in 40 chances, against 2 regressions.** Over all
four rungs it is **10 repairs in 83 chances against 9 regressions in 50** -- a
broken function repaired 12% of the time it could be, a working one broken 18%,
and the sign test on the 19 discordant pairs at p = 1.000. The 8B's probe-clean
count rises across its run, 3 to 5 of 10, the largest rise recorded, and it
supplies 33 of the 83 repair chances -- more than the other three rungs
together -- without beating its own breakage rate. On the 4B specifically,
**0 repairs in 20 chances and 0 regressions** -- the one capable chain was
capable before any feedback existed, and twenty revisions left the other four
broken.

**The mechanism is visible at the level of terms.** The 4B's revisions repaired
6 individual terms and broke 7, and produced *no* function-level repair at all,
because capability is a conjunction: a function with two broken terms that fixes
one is still broken. Revision operates on terms with a roughly equal chance of
breaking another, which is a random walk that does not reach "all four correct".

Two of the three verdict changes in the whole corpus are revisions *destroying*
a capability the function already had.

Full write-up:
[docs/findings/the-loop-does-not-repair-capability.md](findings/the-loop-does-not-repair-capability.md).

```bash
uv run python analysis/term_diagnostics.py runs/published/4b-loop/functions
```

### The loop shows nothing on a second rung

The 4B over 6 iterations on 5 independent chains, 2 h 22 m, same seed splits as
the 14B's five-chain run so the curves are directly comparable. This is the
**second rung ever taken past iteration 0**, and the first check on whether the
findings above describe the loop or describe the 14B.

| chain | it0 | it1 | it2 | it3 | it4 | it5 | gain |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 1.29 | 4.66 | 4.66 | 4.42 | 4.69 | 4.69 | +3.40 |
| 1 | 0.61 | 4.13 | 4.19 | 4.64 | 5.26 | 13.05 | **+12.44** |
| 2 | 8.25 | 8.92 | 7.28 | 7.14 | 8.25 | 0.00 | −8.25 |
| 3 | 7.49 | 0.44 | 0.44 | 0.44 | 0.44 | 0.44 | −7.05 |
| 4 | 8.35 | 0.27 | 3.14 | 10.47 | 0.67 | 3.72 | −4.63 |
| **median** | **7.49** | 4.13 | 4.19 | 4.64 | 4.69 | **3.72** | **−3.77** |

The median curve **falls**, and the honest reading is that **nothing is
detectable**: the measured paired standard deviation is 8.69, so five chains can
only see changes above **10.88**. Three of five chains ended below where they
started. The starting point is not a fluke -- this run's iteration-0 median of
7.49 matches the ladder's independently measured 7.36 on 15 chains.

**The individual chain worth reading is chain 3.** Its first revision wrote
`total_empty = total_empty(board)`, which shadows the function it calls and
raises `UnboundLocalError` on every scoring call -- 342 sandbox failures per
game. It then carried that line, **verbatim, through five consecutive
revisions**, retuning the coefficients around it each time, while the revise
prompt quoted the interpreter's error back to it three times naming the exact
variable.

That is a sharper version of [finding 4](findings/first-revision-reweights-not-debugs.md).
There the defence "it was never told what was wrong" is available. Here it was
told, in the interpreter's own words, five times.

**It also broke a power assumption of this project's own.** The 4B's paired
standard deviation is **2.39x** its cross-chain spread, where the 14B's is
**0.70x** -- the opposite direction. The 30B's published 14-chain requirement
scales from the 14B's ratio and is now a lower bound. Paired noise has to be
measured per rung.

Full write-up:
[docs/findings/4b-loop-reweights-a-crash-five-times.md](findings/4b-loop-reweights-a-crash-five-times.md).

```bash
uv run tetris-bench loop --model qwen3-4b --chains 5 --iterations 6   # 2h22m
```

### The 30B ships the best function and the worst collapse

6 chains x 6 iterations on `qwen3:30b-a3b`, 3 h 42 m, commissioned as a **power
pilot**: every power claim in this repo had been scaling its paired standard
deviation from the 14B, and the 4B had shown that the scaling can invert.

| chain | it0 | it1 | it2 | it3 | it4 | it5 | gain |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 38.3 | 41.7 | 32.4 | 39.4 | 40.0 | **47.0** | +8.70 |
| 1 | 41.6 | 42.2 | 28.6 | 33.2 | 43.7 | **50.2** | +8.64 |
| 2 | 39.4 | — | 36.3 | 32.2 | 21.3 | 13.5 | **−25.91** |
| 3 | 38.8 | 38.4 | 25.9 | 22.9 | 32.2 | 25.4 | −13.44 |
| 4 | 0.0 | 0.4 | 14.2 | 1.4 | 29.2 | 19.2 | +19.17 |
| 5 | 35.5 | 43.5 | 43.2 | 48.4 | 41.8 | 41.6 | +6.10 |
| **median** | **38.57** | 41.66 | 30.51 | 32.70 | 36.12 | **33.51** | **+7.37** |

Median gain **+7.37** against a minimum detectable gain of **19.16**. A third
rung, a third null.

**The pilot's deliverable is that σ_d cannot be borrowed.** Measured here it is
**16.76**, against the **10.54** this repo had published for the rung -- too low
by 1.59x, which turns "14 to 28 chains" into **34**. All four rungs now have a
measured paired term, and their ratios to their own cross-chain spreads are
**0.70x (14B), 0.84x (8B), 1.07x (30B), 2.39x (4B)**: a 3.4x span with no
constant in it. (The 30B's figure read 1.05x when this pilot was published,
computed against a different denominator than the 4B's and the 14B's were; the
8B run found the mixed definition and the table above uses one throughout.)

**It was also the first run with working functions to refine.** The 30B starts
4 of 6 probe-clean, where the 14B and 4B start mostly broken, so the capability
probes could previously only measure repair. It **ends 4 of 6** -- 3 repairs
against 3 regressions over 28 transitions.

The two mechanisms are legible, and they are the same kind of edit:

```python
# chain 1, the best function in the project: 41.6 -> 50.2
return lines * 100 - holes * 20 - max_height * 5 - bumpiness  # iteration 0
return lines * 10 - holes * 350 - max_height * 15 - bumpiness * 35  # iteration 5

# chain 2, the worst collapse: 39.4 -> 13.5, one character
return lines * 50 + sum_tops - holes * 20 - unevenness * 10 - max_height * 3  # it2
return lines * 50 - sum_tops - holes * 20 - unevenness * 10 - max_height * 3  # it3
```

> **Amended 2026-11-24.** Chain 1's reweighting was explained here and in the
> write-up as going "the direction the classic Tetris weightings go". The 8B
> loop's chain 3 made the same move -- hole penalty up 100x, line reward halved
> -- and lost **23.11** points per piece from the best opening function in that
> run. The direction is therefore not what distinguished this success, and no
> account of what did currently stands.
>
> **Resolved the same day, and the premise was false.** Neither revision was a
> reweighting in the way it read. The 8B's hole-penalty move **gained +6.44** on
> its own; its collapse came from setting `max_h` and `unevenness` to 150 each
> (-18.34 and -29.14 alone). And chain 1 here was a **capability repair** whose
> new weights are worth -3.90 without it.
> [The replay](#the-best-revision-was-a-repair-and-its-predecessor-was-a-lucky-tie-breaker).

`tops[col]` is the row index of the topmost filled cell and **row 0 is the top**,
so a larger `sum_tops` means a lower stack. Iteration 3 inverted it, rewarding
tall stacks; iterations 4 and 5 kept the inversion and retuned the terms around
it. Eval totals fall at every step: 24,710 → 11,470 → 5,810 → 1,860 → 820.

**The same inversion sits inside the second-best function.** Chain 0's iteration
5 scores 47.01 with `score_val -= sum_top * 10.0` in it. It does no harm there
only because a line clear is worth 3,000 and a hole 200, so the inverted term
never decides a placement that matters. The bug is not what separates the best
chain from the worst -- the scale of the terms around it is, which is a property
of the whole function rather than of the edit the model made.

One generation produced nothing at all: it emitted exactly 14,000 output tokens,
the configured `max_tokens`, and was still writing. That is the project's fifth
rejection and its first **length cap** rather than a rule violation. The chain's
lineage survived it -- the loop keeps the last function that played, so the next
iteration revised the one from two steps back.

[The full write-up](findings/the-30b-ships-the-best-function-and-the-worst-collapse.md)
· [the artifacts](../runs/published/30b-pilot/)

### The best-powered null, and the revisions that change nothing

10 chains x 6 iterations on `qwen3:8b`, 7 h 09 m, 60 generations. The fourth
rung, and the largest run in the project: the 8B costs 427 s a generation, so
ten chains fit in a night where they do not on the 14B or the 30B.

| chain | it0 | it1 | it2 | it3 | it4 | it5 | gain |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | 15.63 | 15.37 | 17.60 | 17.74 | 23.45 | 17.48 | +1.85 |
| 1 | 26.20 | — | 38.86 | 38.84 | 39.88 | **39.88** | +13.68 |
| 2 | 0.41 | 0.00 | — | 0.00 | 24.65 | 16.61 | +16.20 |
| 3 | **34.57** | 16.44 | 26.09 | 26.09 | 19.92 | 11.46 | **−23.11** |
| 4 | 0.87 | 0.87 | 0.87 | 0.87 | 0.44 | 1.61 | +0.73 |
| 5 | — | 17.75 | — | 27.10 | — | 37.81 | +20.06 |
| 6 | 0.41 | 0.41 | 1.85 | 2.69 | 0.40 | 0.40 | −0.01 |
| 7 | 0.41 | 0.42 | 0.40 | 0.43 | 0.59 | 0.00 | −0.41 |
| 8 | 18.07 | 25.58 | 24.24 | 25.58 | 23.29 | 21.23 | +3.17 |
| 9 | 21.71 | 25.63 | 25.63 | 35.81 | 34.32 | 36.24 | +14.53 |
| **median** | **15.63** | 15.37 | 20.92 | 21.66 | **23.29** | 17.04 | **+2.51** |

A dash is a generation the validator rejected, so no game ran. Median gain
**+2.51** against a detectable **11.02**, seven chains up and three down, sign
test **p = 0.344**. A fourth rung and a fourth null -- but the first where the
bound is worth quoting: **an 8B gain of eleven points per piece or more is ruled
out, and a gain of five is not addressed.** 193 chains would resolve the +2.51,
49 would resolve a +5.

**Some revisions cannot change anything.** Chain 1's last step rewrote its
function and then scored identically on all thirteen sequences, game for game:

```python
# iteration 4 -> 39.88   (plus a term counting columns filled to all 20 rows)
score_val = (lines_cleared * 100) - (holes * 50) - (max_h * 10) - (std_dev * 10)
# iteration 5 -> 39.88
score_val = (lines_cleared * 200) - (holes * 100) - (max_h * 20) - (std_dev * 20)
```

Doubling every weight of a linear score cannot move its argmax, so this is a
no-op by construction: 428 seconds for a revision incapable of choosing
differently. Counting adjacent pairs where both functions are alive and both
score identically on every held-out sequence: **4B 2/14, 8B 6/28, 14B 0/22, 30B
0/26 -- 8 of 90, all on the two small rungs**, every one a different source SHA
and so a genuine rewrite rather than a resubmission. Three of the 8B's six are
one chain sitting a hair above the dead line, so the clear count is five.

**Checked at the decision level, that count is exact rather than a floor.**
Replaying every pair over the same boards -- the game driven by the earlier
function, both asked about each board it reaches -- gives **8 of 94 live
revisions that never once chose differently**, and they are the same eight
pairs, with no disagreement in either direction. The 14B managed 0 of 17 and the
30B 0 of 27, so two independent measures split the rungs the same way.

What that measure adds is a **near-inert class the totals miss**: six more
revisions changed between one and three decisions, which is not a tie because a
few different choices move a total. The sharpest is 8B chain 1's step from
iteration 3 to 4 -- **3 decisions out of 1,949, worth +1.04 points per piece**,
or 41% of the median gain the entire 8B loop showed. A curve moving at that
scale is measuring a handful of placements. Median share of decisions a revision
changes, by rung: **4B 7.4%, 8B 3.3%, 14B 3.7%, 30B 12.8%** -- not a ladder, but
the rung that starts with working functions rewrites them hardest.

```bash
uv run python analysis/placement_diff.py
```

The mechanism is not uniform scaling -- only chain 1's was. Two others moved
their weights *non-uniformly*, by factors of four and five, and still changed
nothing, because `lines_cleared` decides whenever it is non-zero and the
remaining terms kept their ratios to each other. **The model is tuning the
numbers that never decide anything**, which is a sharper account of a flat curve
than "it is all noise".

**All five rejections were `import math`**, four of them at revision steps --
which overturns the claim that
[revisions never do that](#the-import-rule-fails-two-times-in-five). One chain
imported at iterations 0, 2 and 4, was told each time in the validator's own
words, and complied at 1 and 5; half its budget produced nothing. And its three
playing functions rose 17.75 → 27.10 → 37.81, each written immediately after a
rejection, with no game feedback in the prompt at all. Across the run, the four
steps whose feedback was a rejection message gained a mean **+8.18** against
**+0.34** for the 41 steps that got a full game report (permutation p = 0.032;
p = 0.027 against a span-matched control, p = 0.098 with one observation per
chain). **A hypothesis, not a result** -- found after the fact, n=4 -- and one
that 12 chains a group would settle.

Two cheap by-products. The 8B's best function reaches 39.88 points per piece,
**below the hand-written heuristic's 43.34**, and no 8B game was censored, so
unlike the 30B's figures these rates are uncensored throughout. And comparing
this log with the ladder's, **2 of 10 iteration-0 generations reproduced
byte-for-byte** under the same prompt and per-chain seed at temperature 0.7 --
while the *distribution* reproduced closely (median 15.63 against 15.67,
spread 13.09 against 13.36), so a rung's noise is stable even where its samples
are not.

[The full write-up](findings/the-best-powered-null-and-the-inert-revisions.md)
· [the artifacts](../runs/published/8b-loop/)

### The best revision was a repair, and its predecessor was a lucky tie-breaker

Two revisions moved their weights the same direction -- hole penalty up, line
reward down -- and ended in opposite places: the 30B's chain 1 at **41.55 ->
50.19** points per piece, the 8B's chain 3 at **34.57 -> 11.46**. Both documents
recorded the same open question. A term-level replay -- hold each function's
structure fixed, change only its numbers, replay on the ten held-out seeds --
says the question had a false premise.

**The 30B's revision changed three things, not one.** Its iteration 0 computed
column heights by scanning *up* from row 19 and stopping at the first filled
cell, so on any board resting on the floor every height was `19 - 19 = 0`: the
height and bumpiness terms were dead, as the capability probes had already
recorded (`height: blind`). Crossing the repair against the reweighting, with
iteration 0 as the baseline:

| | |
|---|---:|
| repair alone, weights unchanged | **+3.25** |
| reweighting alone, heights still dead | **-3.90** |
| both together | +9.16 |
| **interaction** | **+9.81** |

The new weights make the broken function *worse*, and are worth +5.91 only once
the terms they weight are alive. So the project's best function came from a
**capability repair** -- the one thing the loop has been shown to do -- and the
"only clean example of a revision getting a weighting right" is withdrawn. That
run's own probe data had counted this chain as one of its three repairs, in a
different section of the same document.

**Iteration 0, meanwhile, was 63% tie-breaker.** Remove its trailing
`unique_term` and it scores **15.29** rather than 41.55. With dead height terms
the function is `lines * 100 - holes * 20`, which ties at the maximum on **55%
of decisions**, so a term worth at most 0.199 was not breaking ties, it was the
policy -- and since `row` is the piece's top row on a board whose row 0 is the
top, it preferred *lower* placements:

| trailing term | pts/piece | tied at max |
|---|---:|---:|
| none | 15.29 | 55% |
| `(row*10 + column) * 0.001` -- as written | **41.55** | 0% |
| `row * 0.001` -- prefers low | **42.88** | 25% |
| `-row * 0.001` -- prefers high | **13.92** | 14% |
| `column * 0.001` -- ties broken, no height info | 22.46 | 2% |

Breaking ties at all is worth +7.17; preferring *low* adds +20.42. The model
wrote a uniqueness hack and accidentally encoded the only strategy a
height-blind function could have.

**And the 8B's collapse was not the lines-and-holes move either.** Only its
weights changed, so each one can be walked from its old value to its new one:

| weight moved | from -> to | pts/piece | delta |
|---|---|---:|---:|
| *(iteration 0)* | | 34.57 | |
| `lines` | 100 -> 50 | 34.57 | **+0.00** |
| `holes` | 1 -> 100 | **41.02** | **+6.44** |
| `max_h` | 0.5 -> 150 | 16.23 | **-18.34** |
| `unevenness` | 0.1 -> 150 | 5.44 | **-29.14** |

**The part that matched the 30B's direction is the part that helped.** The
collapse came from the two surface terms at 150 each -- three times a line clear
-- and reverting `unevenness` alone recovers +15.14 of the 23.11 lost. The
result is a function that will not take a line if it raises the stack, which on
a ten-wide board is most lines.

So there was never a direction producing two outcomes. One revision also
repaired its terms; the other also crushed its surface terms.

[The full write-up](findings/the-best-revision-was-a-repair.md)
· [the 23 variants](../runs/published/reweighting/)

```bash
uv run python analysis/reweighting.py
```

### Direct mode costs 800x and plays like random

The milestone 7 demonstration: `qwen3-14b` picking placements one at a time,
one model call per piece, on piece seed 1 at a 20-piece budget. The point was
to measure the cost ratio that makes `strategy` the main mode. It took **3 h
44 m** to place 20 pieces.

| agent | score | lines | holes | max height | cost |
|---|---:|---:|---:|---:|---:|
| heuristic (Lee 2013) | **800** | **7** | **1** | **4** | ~0 s |
| **direct, qwen3-14b** | 0 | 0 | **86** | 19 | **3 h 44 m** |
| random (agent seed 0) | 0 | 0 | 76 | 19 | ~0 s |

**The cost first, since that was the deliverable.** 6,444 output tokens and
**672 s per piece**, against the same model in `strategy` mode at 100.8 tokens
and 10.25 s per piece charged conservatively against a single game, or 8.04 and
0.818 amortised the way the runs actually replay a function. That is **64x to
822x** depending on which denominator you accept. At 672 s per piece a full
2,000-piece game is **15.4 days**, which is why this mode is a demonstration and
not a rung.

**Then the part that was not the goal.** Nearly four hours of 14B generation
bought placements inside the random distribution: random play on this seed makes
70.6 holes on average over 200 agent seeds (median 70, range 33-127), putting
the agent's 86 at about the 80th percentile. Worse than four random games in
five, and comfortably inside the spread -- so "indistinguishable from random,
leaning bad", not "worse than random", which one game cannot establish. The zero
score proves nothing on its own, because random scores zero on all 200 seeds at
this budget; the heuristic's 800 points and 1 hole on the identical sequence is
what shows the budget permits scoring.

**And formatting was not the failure: 0 invalid replies in 20 calls.** The agent
asks for an index into the enumerated legal moves, so every option is legal by
construction and a bad result cannot be blamed on malformed output. The same
model in `strategy` mode rates 24.53 points per piece across every published
run. It can say which move it wants; it just wants the wrong one.

Full write-up, including why per-piece latency turned out *not* to grow with the
board, in
[docs/findings/direct-mode-costs-800x-and-plays-like-random.md](findings/direct-mode-costs-800x-and-plays-like-random.md).

```bash
uv run tetris-bench play --agent heuristic --seed 1 --max-pieces 20   # instant
uv run tetris-bench direct --model qwen3-14b --seed 1 --max-pieces 20 # 3h44m
```

### Findings with their own write-ups

Each of these is a separate experiment in [docs/findings/](findings/), with
the generated functions as artifacts. They are written as the result was found
and corrected in place with a dated note when something later overturned them --
seven of them currently carry one.

- **The first revision reweights instead of debugging.** Two independent
  revisions kept a broken hole count character-for-character and changed only
  weights. Held-out performance flat.
- **A feature-level counterexample fixed what outcome feedback could not** --
  on one trace board in three, so it does not generalise, and the write-up says
  so.
- **Held-out seeds are mandatory.** A fixed, deterministic function varies
  85-348% across unseen seeds. One training-seed score of 400 turned out to be
  that function's luckiest case out of 21, with a held-out mean of 110.
- **Greedy decoding makes a reasoning loop permanent.** The 14B failed to
  terminate on three consecutive attempts, emitting 22,223 tokens with context
  to spare, because Ollama ships temperature 0 with every anti-repetition
  sampler off. In that configuration a loop is *absorbing* and a longer timeout
  just buys a longer loop. A frequency penalty cut the same generation to 7,152
  tokens.
- **At temperature 0 a per-chain seed is inert**, so a five-chain run was four
  copies of one sample.
- **Noise floors** for two rungs, and a **null arm** showing what the curve
  looks like with no feedback at all.
- **[The size ladder is a step, not a
  slope](findings/size-ladder-is-a-step.md)** -- all four rungs at
  iteration 0, 15 chains each, one byte-identical prompt. Also records the
  project's first four rejections, three of which were `import math` against a
  prompt that forbids imports in bold, making them instruction-following
  failures rather than harness artefacts.
- **A bad strategy and one that cannot be expressed look identical in a score**,
  which is why the capability probes exist. Both produce a low number, and 37 of
  60 first attempts were in the second category.
- **[The discriminate warning does not fix inert
  arithmetic](findings/the-discriminate-warning-does-not-fix-inert-arithmetic.md)**
  -- 3 of 123 warned generations are still inert, all 4B, and the only
  controlled pair shows no effect. Also a measurement trap: a one-board probe
  over-reports flatness five-fold.
- **[The import rule fails two times in
  five](findings/the-import-rule-fails-three-times-in-five.md)** -- the
  right denominator is the generations that wanted `math`, not the ones that did
  not. A bolded rule carrying its own worked example, ignored by **8 of the 19
  occasions** in a 227-generation corpus. Its own "revisions never do it" was a
  no-occasion, not a compliance, and is overturned.
- **[The zeros rate does not move
  either](findings/the-zeros-rate-does-not-move-either.md)** -- 5 revivals
  against 5 deaths, p = 1.000, and the sample size that would have been needed:
  15 to 55 chains against the 5 that ran. Over four rungs and 130 transitions it
  is **14 revivals against 11 deaths, p = 0.690**.
- **[The loop does not repair capability
  either](findings/the-loop-does-not-repair-capability.md)** -- 1 repair in
  40 chances against 2 regressions on the first two rungs, and **10 in 83
  against 9 in 50** over all four rungs. A broken function is repaired 12% of
  the time it could be; a working one breaks 18%. Closes the question the ladder
  left open.
- **[The 4B loop reweights a crashing function five
  times](findings/4b-loop-reweights-a-crash-five-times.md)** -- the second
  rung past iteration 0. No detectable change, a chain that carried an
  `UnboundLocalError` through five revisions with the traceback quoted back to
  it, and a power assumption of this project's own broken.
- **[The 30B ships the best function in the project and its worst
  collapse](findings/the-30b-ships-the-best-function-and-the-worst-collapse.md)**
  -- the power pilot. A measured paired σ_d of 16.76 against the 10.54 this repo
  had published, which turns a 14-28 chain requirement into 34; the first rung
  with working functions to refine, ending with as many as it started; and one
  chain that declined at all five revisions after inverting a sign that sits,
  harmlessly, inside the project's second-best function too.
- **[The best-powered null, and the revisions that change
  nothing](findings/the-best-powered-null-and-the-inert-revisions.md)** --
  the fourth rung, and the largest run in the project: 10 chains, a measured
  σ_d of 12.44, median gain **+2.51** against a detectable 11.02. It also found
  revisions that **cannot** change anything -- 8 live revisions rewrote their
  weights and then never once chose differently on any board of ten full games,
  all 8 on the two small rungs, one of them provably so, with 6 more changing at
  most one decision in two hundred -- and a counterexample that costs the 30B
  pilot its explanation for its single success.
- **[The best revision was a repair, not a
  reweighting](findings/the-best-revision-was-a-repair.md)** -- a
  term-level replay of the project's two contrasting reweightings. The 30B's
  winning chain had **dead height terms** at iteration 0, and its new weights
  are worth **-3.90** without the repair that came with them; its predecessor's
  41.55 was **63% an accidental tie-breaker** that preferred low placements. The
  8B's collapse came from its surface weights, not from the lines-and-holes move
  that gained +6.44 on its own. Closes the open question by dissolving it.
- **[Direct mode costs 800x and plays like
  random](findings/direct-mode-costs-800x-and-plays-like-random.md)** --
  the milestone 7 demonstration. 3 h 44 m for 20 pieces, 86 holes against random
  play's 70.6, and 0 malformed replies, so the failure is choice and not
  formatting.

### Not done

Ordered by whether it would change anything claimed above.

**Every rung has now run, and all four are null.** The 14B, the 4B, the 30B and
the 8B have each been taken past iteration 0 under the identical protocol, and
none produced a detectable change. There is no longer an outstanding experiment
that could move a headline by adding coverage; what is left would move one by
adding *power*, and the cost is now known per rung rather than estimated.

- **An adequately powered curve, on the 8B.** 49 chains to resolve a +5 (about
  6 hours of 8B time), 193 to resolve the +2.51 it measured. Every other rung is
  several times dearer for the same resolution -- the 30B needs 34 chains at
  roughly 20 hours to resolve its +8.04 -- so if one powered run gets made, the
  8B is where it goes. See
  [the power analysis](findings/30b-loop-is-underpowered-not-futile.md).
- **The post-rejection effect**, which the 8B run turned up and could not
  settle: revisions written with the feedback removed moved further than
  revisions given a full game report (p = 0.032, n=4, found after the fact).
  Twelve chains a group with the rejection *scripted* rather than waited for,
  about 8.5 hours. It is the one open question whose answer would be
  uncomfortable either way. See
  [the write-up](findings/the-best-powered-null-and-the-inert-revisions.md).

**Two cheap analyses are left**, both answerable from the logs on disk with no
GPU at all.

- ~~**Count placements chosen differently**, rather than exact score ties.~~
  **Done** (`analysis/placement_diff.py`). The lower bound turned out tight --
  the same 8 pairs, no disagreement either way -- so the published count stands.
  It added a near-inert class of 6 more revisions, a per-rung rate of change, and
  the warning that too few seeds over-reports inertness.
- ~~**What separates a good reweighting from a fatal one.**~~ **Done**
  (`analysis/reweighting.py`). The question had a false premise: the 30B's gain
  was a capability repair, and the 8B's lines-and-holes move gained +6.44 while
  its surface weights lost 47. What is left, and sharper: **a grid over the hole
  penalty and the two surface weights on a repaired structure**, to say whether
  there is one ridge both models were walking along. Same corpus, no GPU.

**Two are held rather than planned.**

- **The counterexample arm, rerun on the fixed script (~4.2 h).** The
  per-board reading was withdrawn when the sweep turned out never to have varied
  its seed; the board question reopened at **Fisher p = 0.07 one-sided**, which
  is suggestive and not settled. See
  [the write-up](findings/counterexample-is-the-sampler-not-the-board.md).
- **Is `qwen3-8b` reproducible?** Partly answered for free: comparing the 8B
  loop's log with the ladder's shows **2 of 10 iteration-0 generations
  byte-identical** under the same prompt and per-chain seed. A dedicated run
  (19-30 minutes) would add the revise prompt, which no rung has been shown
  reproducible on.

**Three will not happen here, and the reasons are structural rather than
scheduling.**

- **A powered direct-mode arm.** Several seeds across several rungs, at 672 s
  per piece, is weeks of wall clock for a baseline whose purpose is to be beaten.
  The demonstration ran, the cost ratio was the deliverable, and it is measured
  -- see [above](#direct-mode-costs-800x-and-plays-like-random).
- **Separating size from architecture.** The one rung that outperforms is the one
  MoE, and nothing that fits in 32GB breaks that tie.
- **Raising the piece limit.** Stopped being blocking when the headline moved to
  a rate, which is not censored by the budget. The budget still caps how much
  play any single figure covers -- the best chain's rate rests on about 1,000
  pieces against the heuristic's 10,467 -- so a longer run would tighten that
  comparison rather than fix anything broken.

### Provenance

**Every finding above is checkable from the repo without running a model.**
[`runs/published/`](../runs/published/) holds the generated functions plus the
prompt, reasoning trace and raw reply that produced each one -- including the
full size ladder (60 generations, 728 games) and the five-chain sweep, so the
tables in this section can be rebuilt rather than taken on trust:

```bash
uv run python analysis/curves.py --log runs/published/five-chain/loop.jsonl
uv run python analysis/term_diagnostics.py runs/published/ladder/functions
```

A saved function replays in well under a second, with no model involved. The
`.json` beside each `.py` is the part that makes a claim auditable rather than
merely reported: it holds the prompt the model actually received and the
reasoning trace it actually produced. Working output stays gitignored; this
directory is the deliberate exception, and
[its own README](../runs/published/README.md) indexes what each run supports.

