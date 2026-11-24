# The best-powered null, and the revisions that change nothing

**Date:** 2026-11-24 · **Model:** `qwen3-8b` (`qwen3:8b`, Ollama, temperature 0.7)
**Run:** 10 chains × 6 iterations, 7 h 08 m, 60 generations, zero dollars
**Sources:** [`runs/published/8b-loop/`](../../runs/published/8b-loop/) — 730 rows, 60 functions
**Prompt:** `strategy_v3`, SHA `f3a0cb0af765`, byte-identical to every other run

The fourth and last rung of the ladder, and the first run large enough to be
called powered rather than exploratory. Ten chains was chosen because the three
earlier loops had each ended with the same sentence — *the gain is inside the
noise, and n was too small to say more* — and because the 8B is cheap enough
(427 s a generation) that ten chains fit in a night.

**The curve is null again, and this time the null has a number.** It also turned
up two things the three smaller runs could not: a measurable count of revisions
that rewrite the function and change *not one decision*, and a correction to a
finding published yesterday.

---

## 1. The curve

Held-out rate, points per piece, 10 unseen sequences per position. A dash is a
generation the validator rejected, so no game ran; it is excluded rather than
entered as a zero.

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

Seven chains up, three down. The median gain is **+2.51** against a minimum
detectable gain at n=10 of **11.02**, and an exact sign test on the directions
gives **p = 0.344**. Four rungs, four nulls.

The best function in the run is chain 1's last, at **39.88 points per piece** —
below the hand-written heuristic's 43.5 and well below the 30B's 50.19. No 8B
game was censored: the best one survives about 201 pieces, a tenth of the
2,000-piece budget, so unlike the 30B's figures these rates are uncensored
throughout.

### Why this null is worth more than the three before it

| rung | chains | median gain | σ_d | MDE at that n |
|---|---:|---:|---:|---:|
| `qwen3-4b` | 5 | −4.63 | 8.69 | 10.88 |
| **`qwen3-8b`** | **10** | **+2.51** | **12.44** | **11.02** |
| `qwen3-14b` | 5 | +8.04 | 8.74 | 10.95 |
| `qwen3-30b` | 6 | +7.37 | 16.76 | 19.16 |

Every σ_d in that table is now **measured, not scaled** — the 8B was the last
rung without one. What the 8B adds is the first case where the observed gain is
small *relative to what the run could have seen*: the 14B's +8.04 and the 30B's
+7.37 are both large enough that a modestly bigger run might have resolved them,
whereas +2.51 at an MDE of 11.02 would need **193 chains** to call real, and 49
chains merely to resolve a +5.

So the honest claim is bounded, not absolute: **this run rules out an 8B
improvement of 11 points per piece or more, and says nothing about a gain of
five.** That is the tightest bound the project has.

---

## 2. The scaling method stays retired, and the ratios need one definition

Yesterday's 30B pilot retired the practice of scaling a rung's paired σ_d from
the 14B's, on the strength of three ratios spanning 3.4×. With the fourth
measured, recomputed by one piece of code over all four logs:

| rung | σ_d | cross-chain spread | ratio |
|---|---:|---:|---:|
| `qwen3-4b` | 8.69 | 3.63 | **2.39×** |
| `qwen3-14b` | 8.74 | 12.55 | **0.70×** |
| `qwen3-8b` | 12.44 | 14.89 | **0.84×** |
| `qwen3-30b` | 16.76 | 15.70 | **1.07×** |

Three rungs sit between 0.70 and 1.07 and the 4B sits at 2.39. Tempting to read
that as "the scaling works except on the 4B", and the temptation should be
resisted: the 4B is the rung where most functions are dead, so its cross-chain
spread is small because nearly every chain scores near zero, not because its
generations agree. A rule that holds on three rungs and inverts on the fourth is
not a rule, and nothing here predicts which rung a fifth model would behave
like.

> **Correction (2026-11-24).** Yesterday's pilot reported the 30B's ratio as
> **1.05×**, computed against the standard deviation of the iteration-0 rates.
> The 4B's 2.39× and the 14B's 0.70×, published earlier, are computed against
> `Curve.chain_spread()` — the project's own unit-tested statistic, which
> averages the between-chain spread over every iteration rather than using the
> first. Two definitions of one denominator were being compared across runs.
> The table above uses `chain_spread()` throughout, which moves the 30B's figure
> to **1.07×**. The conclusion is unchanged under either definition (the span is
> 3.4× one way and 3.7× the other), but the mixed denominator is exactly the
> kind of error that makes a cross-run comparison mean nothing, so it is
> recorded rather than quietly fixed.

---

## 3. A revision that cannot change anything

Chain 1's last step rewrote its scoring function and scored **80,000 points over
2,006 pieces** — the same total, over the same number of pieces, on all ten
held-out sequences as the function before it.

```python
# iteration 4 -> 39.88
completely_filled_columns = sum(1 for c in range(10) if all(board[r][c] for r in range(20)))
score_val = (lines_cleared * 100) - (holes * 50) - (max_h * 10) - (std_dev * 10) - (completely_filled_columns * 10)
# iteration 5 -> 39.88
score_val = (lines_cleared * 200) - (holes * 100) - (max_h * 20) - (std_dev * 20)
```

Every weight is doubled and one term is dropped. **Doubling every weight of a
linear score cannot change which placement is the maximum**, so the only way
these two functions could ever disagree is through the dropped term — and the
identical totals on all thirteen sequences show it never decided anything
either. This revision is a no-op by construction, not by luck. The model spent
428 seconds producing it, and the feedback it was handed reported the identical
game it had just played.

It is not alone. Counting adjacent pairs where both functions are alive and
both score identically on every one of the ten held-out sequences:

| rung | inert / live adjacent revisions |
|---|---|
| `qwen3-4b` | 2 / 14 |
| `qwen3-8b` | 6 / 28 |
| `qwen3-14b` | 0 / 22 |
| `qwen3-30b` | 0 / 26 |

**Eight of 90 live revisions across the corpus changed nothing, and all eight
are on the two small rungs.** Every one has a different source SHA, so none is
a resubmission — each is a genuine rewrite that is behaviourally inert.

Two caveats, both load-bearing. First, **three of the 8B's six are chain 4**,
whose rate is 0.87 points per piece against a `RANDOM_CEILING` of 0.851: it is
classified alive by a hair and is really a dead function being retuned, so the
defensible count is **five clear cases, three on the 8B**. Second, identical
totals over ten sequences is overwhelming evidence of identical play but not a
proof, except for chain 1 where the algebra settles it.

The mechanism is the interesting part, and it is not uniform scaling — only
chain 1's was. The other two 8B cases moved their weights *non-uniformly* and
still changed nothing:

```python
# chain 3, it2 -> it3, both 26.09: lines falls from 100x a hole to 25x a hole
score_val = lines_cleared * 1000 - holes * 10 - max_h * 5  - unevenness * 5
score_val = lines_cleared * 500  - holes * 20 - max_h * 10 - unevenness * 10
# chain 9, it1 -> it2, both 25.63: three weights move 2x, two move 5x
score_val = lines * 100 - holes * 5  - max_col_height * 5  + top_empty * 1 - std_dev * 1
score_val = lines * 100 - holes * 10 - max_col_height * 10 + top_empty * 5 - std_dev * 5
```

In both, the term that decides is `lines_cleared`, and it decides whenever it is
non-zero no matter which of these weights is used; the remaining terms keep
their ratios to *each other*, so they break ties exactly as before. **The model
is tuning the numbers that never decide anything.** That is a sharper statement
of why these curves are flat than "it is all noise": a fifth of the small rungs'
revisions are not noisy, they are arithmetically incapable of being anything.

### Measured at the decision level: the lower bound was tight

> **Added 2026-11-24 (later the same day).** Everything above counts **exact
> ties in the held-out totals**, which this document called "a lower bound by
> construction" and §10 listed as worth replacing with a count of *placements
> chosen differently*. That measurement has now been run
> (`analysis/placement_diff.py`, 304 s, no model calls), and **the bound was
> tight, not loose.** The prediction that motivated the analysis was wrong, and
> the analysis still earned its keep three other ways.

The game is driven by the **earlier** function and both functions are asked
about every board it reaches, so they are always answering the same question;
comparing two independent playouts would instead measure how far the
trajectories drifted after their first disagreement. The rate is therefore "how
often would the revision have chosen otherwise, in the situations its parent
gets into", and it is a floor rather than an effect size: one early divergence
changes every board after it.

**129 revisions compared, 94 of them between two live functions.**

| | |
|---|---:|
| changed **no decision at all** | **8 of 94** |
| changed fewer than 1 in 200 | 6 more |
| scored identically on the totals (the test above) | **8** |

**The two sets are the same eight pairs, with no disagreement in either
direction.** Among live revisions, scoring identically on ten held-out
sequences and never once choosing differently turn out to be the same event, so
the published 8 needs no revision upward. Six further pairs among the dead
functions are also inert, and also exact ties.

Inertness stays confined to the small rungs under the new measure too, which is
the useful part: **8 of 8 are 4B or 8B, while the 14B managed 0 of 17 and the
30B 0 of 27.** Two independent measures, same split.

### What it added, since the headline did not move

**A near-inert class the totals genuinely do miss.** Six revisions changed
between one and three decisions and are not ties, because a handful of different
choices moves a total:

| revision | decisions changed | rate | points per piece |
|---|---|---|---:|
| `qwen3-8b` chain 1, it3→it4 | **3 of 1,949** | 1 in 649 | 38.84 → **39.88** (+1.04) |
| `qwen3-8b` chain 9, it3→it4 | 2 of 1,712 | 1 in 856 | 35.81 → 34.32 (−1.48) |
| `qwen3-8b` chain 1, it2→it3 | 2 of 2,002 | 1 in 1,001 | 38.86 → 38.84 (−0.02) |
| `qwen3-14b` chain 3, it2→it3 | 2 of 826 | 1 in 413 | 25.42 → 26.12 (+0.69) |
| `qwen3-14b` chain 0, it2→it3 | 3 of 621 | 1 in 207 | 18.04 → 18.07 (+0.03) |
| `qwen3-30b` chain 5, it4→it5 | **1 of 3,086** | 1 in 3,086 | 41.77 → 41.63 (−0.14) |

So **14 of 94 revisions (15%) changed at most one decision in two hundred**, and
unlike exact inertness this class reaches the top two rungs. The first row is
the one to keep: **three choices out of 1,949 produced +1.04 points per piece**,
which is 41% of the median gain the whole 8B loop showed. A curve built on
movements of that size is measuring a handful of placements, which is a more
specific statement of why the noise bar is what it is.

**How much a revision normally changes, by rung.** Median share of decisions
changed: **4B 7.4%, 8B 3.3%, 14B 3.7%, 30B 12.8%** (pooled 8.3%, range 0% to
78%). Not a ladder — the 4B is above the 8B and the 14B — but the 30B's
revisions move about four times as many decisions as the middle rungs', so the
rung that starts with working functions also rewrites them most aggressively.
That sits awkwardly beside its three regressions and is the most likely place to
look next.

**A sampling trap, worth recording because it nearly became the result.** A
two-seed trial of this same measure reported **10** of the 8B's 31 live
revisions as inert; ten seeds give **6**. Four of the ten were artefacts of
having too few boards to disagree on, in the same way that
[a one-board probe over-reports flatness five-fold](the-discriminate-warning-does-not-fix-inert-arithmetic.md).
Inertness is a claim about *every* board, so it can only ever be over-reported
by sampling fewer of them.

---

## 4. The import rule: revisions do it too

All five of this run's rejections are the same thing, in the validator's own
words:

```
line 1: imports are not allowed (found math);
        'math' is already available without importing it
```

[`the-import-rule-fails-three-times-in-five.md`](the-import-rule-fails-three-times-in-five.md)
argued — correctly — that the denominator is the finding: only the generations
that *want* `math` have occasion to obey the rule. Recomputed over the whole
227-generation corpus, with the 30B pilot and this run included:

| condition | occasions | imported |
|---|---:|---:|
| iteration 0 | 7 | **4** (57%) |
| revisions | 12 | **4** (33%) |
| **all** | **19** | **8** (42%) |

Two things change. The headline rate softens from **3 of 5 (60%)** to **8 of 19
(42%)** on a denominator nearly four times larger — still a bolded instruction
that carries its own substitute and a worked example being ignored two times in
five.

And **section 4 of that finding is overturned.** It reported "revisions never do
it, 0 in 55" and reasoned that a revision has the previous function to copy
where iteration 0 has only prose. That reasoning was built on a zero which was
really a *no occasion*: every one of the five known occasions happened to be at
iteration 0. With 12 revision occasions now on record, 4 of them imported, and
Fisher's exact test on 4/7 against 4/12 gives **p = 0.377**. There is no
detectable difference between the conditions.

The finding's own insistence on the right denominator, applied one level deeper
than it was applied.

### The error message works, and only until the next step

Chain 5 is the whole phenomenon inside one chain. It is told the rule by the
prompt, then by the validator, three times:

| iteration | reached for `math`? | outcome |
|---|---|---|
| 0 | yes | **imported — rejected** |
| 1 | yes | used `math.sqrt` correctly, played 17.75 |
| 2 | yes | **imported — rejected** |
| 3 | no | played 27.10 |
| 4 | yes | **imported — rejected** |
| 5 | yes | used `math.sqrt` correctly, played 37.81 |

Half its budget — three generations, 20,691 output tokens, 1,325 seconds —
produced nothing. And the pattern is exact: **it complies at every step whose
feedback was the rejection message, and violates at every step whose feedback
was a game report.** Across the run, 0 of the 5 steps immediately following a
rejection imported, against 4 of the other 45 revisions.

The counterweight, for honesty: the 30B's chain 5 used `math.sqrt` correctly at
all six of its iterations without ever being told. One chain each way, and 0 of
5 is not a significant rate. What this is not is a reason to change the
sandbox — rejecting the import is correct, and the AST layer exists so that a
violation costs one generation instead of a timeout, which is what it cost.

---

## 5. The steps with no feedback moved the most

Chain 5 rises monotonically — 17.75, 27.10, 37.81 — and every one of those three
functions was written immediately after a rejection, so the only feedback in its
prompt was:

```
## Your code was rejected before it could run

line 1: imports are not allowed (found math); 'math' is already available without importing it

Nothing was played, so there are no results to report. Fix the problem above and try again.
```

No score, no board, no cause of death. Chain 1's largest jump (+12.66, the
biggest single step in the run) has the same shape. Measured against the last
rate each chain recorded:

| step type | n | mean Δ | median Δ |
|---|---:|---:|---:|
| feedback was a rejection message | 4 | **+8.18** | +10.03 |
| feedback was a full game report | 41 | **+0.34** | 0.00 |

A permutation test on the difference of means gives **p = 0.032**. The obvious
confound is span — a post-rejection step covers two generations, not one — and
it does not explain it: against the 31 two-step gaps with no rejection between
them (mean +1.07), the difference is **+7.11, p = 0.027**.

**This is a hypothesis, not a result, and it should be read as one.** It was
found by looking at the data after the fact, it is one of many comparisons this
log would support, and two of the four observations come from chain 5. Taking
one observation per chain — the conservative correction for that clustering —
leaves n=3 and **p = 0.098**.

It is also cheap to settle, which is the reason to write it down. A
pre-registered arm that scripts one rejection into every chain at a fixed
iteration needs **12 chains per group** for 80% power at the observed +7.11, or
about 8.5 hours at three iterations a chain. If it held up it would be the most
uncomfortable result in the project: that the loop's revisions move more when
the feedback is removed.

---

## 6. A counterexample to the 30B's one success

Yesterday's pilot held up 30B chain 1 as the project's only clean example of
outcome feedback producing a correct reweighting, and explained it by direction:
the hole penalty rose 17.5× while the line reward fell 10×, *"the direction the
classic Tetris weightings go — survive, do not chase lines"*.

8B chain 3 made the same qualitative move and lost 23.11 points per piece, the
worst collapse in this run, starting from the best opening function in it:

```python
# iteration 0 -> 34.57   a line is worth 100 holes
score_val = lines_cleared * 100 - holes * 1   - max_h * 0.5 - unevenness * 0.1
# iteration 5 -> 11.46   a line is worth half a hole, and a third of the height it costs
score_val = lines_cleared * 50  - holes * 100 - max_h * 150 - unevenness * 150 - bottom_empty * 100
```

Hole penalty up 100×, line reward halved: the same direction, four times further
on the hole term than the 30B went relative to lines. The result is a function
that will not take a line if it raises the stack, which on a 10-wide board is
most lines.

**So the direction is not what distinguished the 30B's success.** That leaves the
pilot's one positive example without its stated mechanism, and the project
without any account of what separates a good reweighting from a fatal one beyond
"how far". Noted as an open question rather than papered over; it is also one
more reason the 30B's +8.64 should not be read as the loop working.

> **Answered 2026-11-24 (later the same day), and the question dissolved.** The
> term-level replay found that **neither revision was what it looked like, and
> the shared direction helped in both cases.** Walking the 8B's weights one at a
> time from iteration 0: raising the hole penalty 1 → 100 **gained +6.44**, and
> halving the line reward changed nothing measurable. The collapse came from the
> two surface terms, set to 150 each — `max_h` **−18.34** and `unevenness`
> **−29.14** on their own. Reverting `unevenness` alone recovers +15.14 of the
> 23.11 lost. Meanwhile the 30B's chain 1 turned out to be a **capability
> repair**: its iteration-0 height and bumpiness terms were dead, and its new
> weights applied to that broken function are worth **−3.90**. There is no
> puzzle about one direction producing two outcomes, because it did not. See
> [the-best-revision-was-a-repair.md](the-best-revision-was-a-repair.md).

---

## 7. The two side channels, pooled over four rungs

Both checks that the earlier runs used to look for improvement the curve cannot
see were re-run with the 8B included. Both are still null, and both now have
enough transitions to say so with some force.

**Can the loop repair a function that cannot express a strategy?** Probe-clean
counts rise across this run — 3, 2, 3, 4, 5, 5 of 10 — which is the largest
rise recorded, and it survives no further scrutiny:

| rung | repairs / chances | regressions / chances |
|---|---|---|
| `qwen3-4b` | 0 / 20 | 0 / 5 |
| `qwen3-8b` | **5 / 33** | 3 / 17 |
| `qwen3-14b` | 2 / 24 | 3 / 6 |
| `qwen3-30b` | 3 / 6 | 3 / 22 |
| **pooled** | **10 / 83 (12%)** | **9 / 50 (18%)** |

A broken function is repaired 12% of the time it could be, and a working one
breaks 18% of the time it could. The sign test on the 19 discordant pairs gives
**p = 1.000**. The 8B contributes more repair opportunities than the other three
rungs combined and still does not beat its own breakage rate.

**Does the fraction of functions scoring nothing move?** On the 8B, dead chains
by iteration run 4, 4, 3, 2, 4, 2 of 10 — down two, having been up and down in
between. Pooled over the four loops, 130 adjacent transitions give **14 revivals
against 11 deaths, p = 0.690**.

One caveat on the 8B's figures: chain 4 sits at 0.44–1.61 points per piece
against a ceiling of 0.851, so it crosses the dead line without its behaviour
changing. Three of this run's transitions are that chain, and the pooled count
would read 13 against 10 without it.

---

## 8. Iteration 0 reproduced 2 times in 10

The size ladder ran 13 scoring 8B chains at iteration 0 on 2026-11-23; this
loop ran 10 more the next night, from the same prompt, under the same per-chain
seed, at temperature 0.7. Comparing the two logs costs nothing and answers a question the project had
left open on this rung:

| | ladder | this run | |
|---|---|---|---|
| chain 0 | `6d17050c` 15.63 | `6d17050c` 15.63 | **byte-identical** |
| chain 1 | `3f2a079f` 26.20 | `3f2a079f` 26.20 | **byte-identical** |
| chains 2–9 | — | — | eight different functions |

**2 of 10.** The seed is honoured and the sampler is doing what it is told; the
rest is backend numerics, as `configs/models.yaml` already records for the 4B
and the 30B. Two consequences worth keeping:

- The 8B's iteration-0 distribution itself **does** reproduce, even though
  individual generations mostly do not: 13 ladder chains give a median of 15.67
  and a cross-chain spread of 13.36, and these 10 give **15.63 and 13.09**. The
  rung's noise is a stable property even where its samples are not.
- The two runs are therefore **not independent samples** on chains 0 and 1, so
  pooling the ladder's 8B iteration-0 figures with this run's would double-count
  two of the ten. Nothing above does.

---

## 9. What it cost

| | |
|---|---|
| wall clock | 7 h 08 m 45 s (01:42:35 → 08:51:20 GMT) |
| generations | 60, of which 5 were rejected |
| tokens | 85,936 in, **396,293 out** |
| per generation | mean 427.3 s, median 428.0 s, range 169.5–817.1 s |
| games played | 180 training, 550 held-out, 0 censored, all ended `block_out` |
| sandbox failures | **0**; 0 failed calls; 15 invalid outputs (the 5 rejections × 3 training seeds) |
| dollars | 0.00 |

Generation latency totals 7.12 hours against 7.15 hours of wall clock: **the
games are free and the model is the whole cost**, which is the ratio the
`strategy` mode was designed for and the opposite of `direct` mode's.

Tokens per point of rate is **2,120** and seconds per point is **114**, counting
only the two chains whose gain exceeded the noise bar. Both figures are
arithmetic on a null result and should not be quoted as a cost of improvement.

---

## 10. What would change these answers

- **The curve.** 193 chains to resolve +2.51 on this rung, 49 to resolve +5 —
  about 23 and 6 hours of 8B time respectively. The 8B is the only rung where
  this is affordable at all, which makes it the right place to run the
  project's one adequately powered curve if any gets run.
- ~~**The inert revisions.** The count above is a lower bound: it catches only
  exact ties.~~ **Done, same day** — see the dated section in §3. The bound was
  tight: the same 8 pairs, no disagreement either way. What it added is a
  near-inert class of 6 more, a per-rung rate of change, and the warning that
  too few seeds over-reports inertness.
- **The post-rejection effect.** 12 chains a group, pre-registered, with the
  rejection scripted rather than waited for. §5.
- **The reweighting question** §6 leaves open: what distinguishes the 30B's
  winning reweighting from the 8B's fatal one, given both moved the same
  direction. A term-level replay over a grid of weights would answer it without
  a model, and is the kind of question this corpus is already large enough for.

---

## 11. Reproducing every number above

No model required; all of it is replay and arithmetic, a few seconds.

The decision-level measure in §3 has its own entry point, because it plays
games rather than reading logs:

```bash
uv run python analysis/placement_diff.py              # ~5 min, all four rungs
uv run python analysis/placement_diff.py --runs 8b-loop --seeds 1000 1001
```

Everything else is replay and arithmetic:

```bash
uv run python - <<'PY'
import json, collections, itertools, math, random, re, statistics
from pathlib import Path
from tetris_bench.curves import build_curves
from tetris_bench.term_diagnostics import classify_directory
from tetris_bench.zeros_rate import is_dead

def rates(run):
    rows = [json.loads(l) for l in open("runs/published/%s/loop.jsonl" % run)]
    g = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        if r.get("split") == "eval":
            a = g[(r["chain"], r["iteration"])]
            a[0] += r["score"]; a[1] += r["pieces_placed"]
    return rows, {k: s / p for k, (s, p) in g.items() if p}

# sections 1 and 2
rows, rate = rates("8b-loop")
for c in range(10):
    its = sorted(i for (cc, i) in rate if cc == c)
    print("chain %d" % c, " ".join("%6.2f" % rate[(c, i)] for i in its),
          "gain %+.2f" % (rate[(c, its[-1])] - rate[(c, its[0])]))
print("medians:", ["%.2f" % statistics.median([rate[(c, i)] for c in range(10)
                                               if (c, i) in rate]) for i in range(6)])
for run in ("4b-loop", "8b-loop", "five-chain", "30b-pilot"):
    rws, rt = rates(run)
    chains = sorted({c for c, _ in rt})
    gains = [rt[(c, max(i for (cc, i) in rt if cc == c))]
             - rt[(c, min(i for (cc, i) in rt if cc == c))] for c in chains]
    sd = statistics.stdev(gains); n = len(gains)
    spread = [cv.chain_spread() for cv in build_curves(rws)][0]
    print("%-10s n=%2d  median %+6.2f  sd %5.2f  MDE %5.2f  spread %5.2f  ratio %.2f"
          % (rws[0]["model"], n, statistics.median(gains), sd,
             2.8 * sd / math.sqrt(n), spread, sd / spread))
print("193 chains:", round((2.8 * 12.44 / 2.51) ** 2), " 49 chains:", round((2.8 * 12.44 / 5) ** 2))

# section 3: revisions that changed nothing
for run in ("4b-loop", "8b-loop", "five-chain", "30b-pilot", "clean-6iter"):
    rws, rt = rates(run)
    g = collections.defaultdict(lambda: [0, 0])
    for r in rws:
        if r.get("split") == "eval":
            a = g[(r["chain"], r["iteration"])]
            a[0] += r["score"]; a[1] += r["pieces_placed"]
    inert = live = 0
    for k in sorted(g):
        nxt = (k[0], k[1] + 1)
        if nxt not in g or not g[k][1] or is_dead(rt[k]) or is_dead(rt.get(nxt, 0)):
            continue
        live += 1; inert += g[k] == g[nxt]
    print("%-12s inert %d / %d live revisions" % (rws[0]["model"], inert, live))

# section 4: every occasion to obey the import rule
for f in sorted(Path("runs/published").glob("*/functions/*.py")):
    src = f.read_text()
    if "math." not in src:
        continue
    cond = "iter0" if f.name.endswith("iter0.py") else "revision"
    print("  %-9s %-9s %s" % (cond, "IMPORTED" if re.search(r"^\s*import math", src, re.M)
                              else "correct", f.relative_to("runs/published")))

# section 5: post-rejection steps against two controls
post, plain, two = [], [], []
for c in range(10):
    for i in range(1, 6):
        if (c, i) not in rate:
            continue
        prev = [j for j in range(i) if (c, j) in rate]
        if not prev:
            continue
        (plain if prev[-1] == i - 1 else post).append(rate[(c, i)] - rate[(c, prev[-1])])
    for i in range(2, 6):
        if all((c, j) in rate for j in (i, i - 1, i - 2)):
            two.append(rate[(c, i)] - rate[(c, i - 2)])
def perm(a, b, seed):
    obs = statistics.fmean(a) - statistics.fmean(b); allv = a + b
    random.seed(seed); hits = 0
    for _ in range(200000):
        random.shuffle(allv)
        hits += abs(statistics.fmean(allv[:len(a)])
                    - statistics.fmean(allv[len(a):])) >= abs(obs)
    return obs, hits / 200000
print("post %d mean %+.2f | plain %d mean %+.2f sd %.2f | two-step %d mean %+.2f"
      % (len(post), statistics.fmean(post), len(plain), statistics.fmean(plain),
         statistics.stdev(plain), len(two), statistics.fmean(two)))
print("vs one-step p = %.3f   vs two-step p = %.3f" % (perm(post, plain, 0)[1],
                                                       perm(post, two, 1)[1]))
print("12 per group:", math.ceil(2 * (2.8 * statistics.stdev(plain) / 7.11) ** 2))

# section 7: repairs and deaths, pooled
REP = CHR = BRK = CHB = 0
for run in ("4b-loop", "8b-loop", "five-chain", "30b-pilot", "clean-6iter"):
    res = {}
    for v in classify_directory("runs/published/%s/functions" % run):
        m = re.search(r"chain(\d+)-iter(\d+)", v.label)
        if m:
            res[(int(m.group(1)), int(m.group(2)))] = v.strategy_capable
    for (c, i), ok in res.items():
        if (c, i + 1) not in res:
            continue
        nxt = res[(c, i + 1)]
        if ok:
            CHB += 1; BRK += not nxt
        else:
            CHR += 1; REP += nxt
print("pooled repairs %d/%d  regressions %d/%d" % (REP, CHR, BRK, CHB))

# section 8: what reproduced
def it0(run):
    return {r["chain"]: r["function_sha"] for r in
            (json.loads(l) for l in open("runs/published/%s/loop.jsonl" % run))
            if r["model"] == "qwen3-8b" and r["iteration"] == 0}
a, b = it0("ladder"), it0("8b-loop")
print("identical at iteration 0:",
      sum(1 for c in set(a) & set(b) if a[c] == b[c]), "of", len(set(a) & set(b)))

# section 9: cost
seen = {}
for r in rows:
    k = (r["chain"], r["iteration"])
    if r["tokens_out"] and k not in seen:
        seen[k] = (r["tokens_in"], r["tokens_out"], r["latency_seconds"])
lat = [v[2] for v in seen.values()]
print("%d generations, %d in, %d out, mean %.1fs, total %.2fh"
      % (len(seen), sum(v[0] for v in seen.values()), sum(v[1] for v in seen.values()),
         statistics.fmean(lat), sum(lat) / 3600))
PY
```
