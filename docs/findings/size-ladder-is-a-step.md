# Finding: the size ladder is a step, not a slope

**Date:** 2026-11-22 · **Models:** `qwen3:4b`, `qwen3:8b`, `qwen3:14b`, `qwen3:30b-a3b`
**Template:** `strategy_v3` · **Iterations:** 1 (iteration 0 only) · **Chains:** 15 per rung
**Temperature:** 0.7 · **frequency_penalty:** 0.5 · **max_tokens:** 14,000 · **max_retries:** 0
**Train seeds:** 1, 2, 17 (fed back) · **Eval seeds:** 1000–1009 (held out) · **Piece limit:** 2,000
**Log:** `runs/ladder.jsonl` (740 rows) · **Functions:** `runs/functions/ladder/` (60)

The capability-ladder experiment from milestone 8. Four rungs of the same model
family, same prompt, same seeds, 15 independent chains each, no feedback — this
measures what each rung writes *cold*, before the improvement loop touches it.

**The prompt was byte-identical across all 60 generations** (SHA `f3a0cb0af765`),
so the only variable is the model. That is the whole point of the config change
that preceded this run, and it is worth verifying rather than assuming.

---

## 1. Result

| rung | played | probe-clean | median pts/pc | best pts/pc | median total | best total |
|---|---:|---:|---:|---:|---:|---:|
| `qwen3-4b` | 15/15 | **4/15** | 7.4 | 15.6 | 290 | 880 |
| `qwen3-8b` | 13/15 | **5/15** | 15.6 | 35.1 | 880 | 5,940 |
| `qwen3-14b` | 13/15 | **3/15** | **1.9** | 39.0 | 40 | 9,820 |
| `qwen3-30b-a3b` | 15/15 | **11/15** | **26.0** | **46.4** | 2,580 | 81,300 |
| *hand-written heuristic* | — | — | *43.5* | *43.5* | *84,720* | *84,720* |

> **Later correction.** Two things changed in this table.
>
> Its medians originally excluded the rejected positions, giving 290 / 940 / 670
> / 2,580 on totals. `analysis/curves.py` counts a rejected position as a zero --
> it failed, which is a result rather than missing data -- and the table now
> follows it. The effect is concentrated on the two rungs that had rejections,
> and it is not small: the 14B's median rate goes from 12.5 to **1.9**, below the
> 4B's. Excluding failures flattered exactly the rungs that failed, which made
> the 14B's weakness look milder than it is.
>
> It also originally led with total score and quoted
> `pts/piece` as a mean of per-game ratios (13.6 / 32.2 / 35.7 / 45.0). The
> headline has since moved to points per piece as a ratio of totals, for the
> reason section 6 gives below: the best function here is censored in 8 of 10
> games, so its total was partly reporting the budget. The ordering of the rungs
> is unchanged and every significance test below stands, since those are computed
> on the probe-clean counts rather than on scores.

Scores are per-chain means over the ten held-out sequences, and `pts/piece` is
**total points over total pieces**, which is what the hand-written baseline's own
43.5 is (454,900 / 10,467). Note the best chain by rate is not the best by score:
on the 30B that is chain 4, not chain 3. "probe-clean" is
[strategy-capable](../../src/tetris_bench/term_diagnostics.py): the function
answers all four capability probes correctly, so its score reflects a strategy
rather than a defect.

**There is no slope across the three dense rungs.** 4B, 8B and 14B are
statistically indistinguishable from one another, and the 14B is *below* both
smaller rungs on capability:

| comparison | probe-clean | Fisher exact |
|---|---|---:|
| 4B vs 8B | 4/15 vs 5/15 | p = 1.00 |
| 4B vs 14B | 4/15 vs 3/15 | p = 1.00 |
| 8B vs 14B | 5/15 vs 3/15 | p = 0.68 |
| 4B vs 30B | 4/15 vs 11/15 | **p = 0.027** |
| 14B vs 30B | 3/15 vs 11/15 | **p = 0.009** |
| 8B vs 30B | 5/15 vs 11/15 | p = 0.066 |
| **30B vs 4B+8B+14B pooled** | 11/15 vs 12/45 | **p = 0.002** |

On chain-mean scores, Mann-Whitney gives the same shape: 30B against the three
dense rungs pooled is p = 0.015, while 4B/8B/14B among themselves are p = 0.07,
0.58 and 0.51.

A Cochran-Armitage trend test over `log2(params)` returns z = 2.37, p = 0.018.
**That number should not be quoted.** A trend test assumes monotonicity, which
the 8B-vs-14B inversion violates; the statistic is produced entirely by the top
rung. The honest summary is a step between the 14B and the 30B, not a slope.

---

## 2. The confound: the step is also the only MoE

`qwen3:30b-a3b` is mixture-of-experts with roughly 3B active parameters. It is
the only non-dense rung, and it is the rung that separates.

So the finding cannot be stated as "capability scales with size". With one
architecture at one size, size and architecture are perfectly confounded, and
three observations of dense scaling (4B → 8B → 14B) show **no** effect at all.
What the data supports:

> Three dense Qwen3 rungs from 4B to 14B are flat on this task. A 30B-a3b MoE is
> decisively better than all of them.

Two further observations are consistent with architecture rather than scale
mattering here, though neither is decisive:

- The 30B is the **fastest** rung — 346s per generation against the 14B's 832s —
  because only ~3B parameters are active per token. It is better *and* cheaper,
  which a pure size story does not predict.
- The same rung is the project's **least reproducible** one
  ([noise-floor-qwen3-30b.md](noise-floor-qwen3-30b.md)), which was already
  attributed to expert-gating sensitivity.

Settling this needs a dense model at or above 30B, which does not fit in 32GB at
a useful quantisation, or a second MoE at a smaller size. Both are out of scope
for this machine; the confound should be stated in the README rather than hidden.

---

## 3. The probes predict a score everywhere except the 4B

The sharper result, and the one that justifies having built the probes at all:

| rung | probe-clean median | probe-broken median | ratio |
|---|---:|---:|---:|
| `qwen3-4b` | 7.1 | 7.5 | **0.9×** |
| `qwen3-8b` | 31.4 | 0.5 | 63× |
| `qwen3-14b` | 24.9 | 0.4 | 62× |
| `qwen3-30b-a3b` | 33.5 | **0.0** | ∞ |
| **pooled (60 chains)** | **26.9** | **1.2** | 22× |

In points per piece, over all 15 positions per rung with a rejected function
counting as zero.

> **Later correction.** Under the old total-score headline these ratios read
> 0.9× / 8.1× / 104× / ∞, which looked like a gradient, and this section was
> titled "the probes gain predictive power with scale". Per piece they read
> 0.9× / 63× / 62× / ∞ — the 8B and the 14B are indistinguishable, so it is a
> **step at the 4B boundary rather than a gradient**. The old progression was an
> artefact of totals: score grows superlinearly with survival, so a rung whose
> clean functions survive longer got a disproportionately larger ratio. The
> finding that survives is the one the 4B supports on its own, and it is the
> interesting half anyway.

Pooled, that separation is p = 0.000001 (Mann-Whitney). From the 8B up, whether
a function can express a strategy at all is most of what determines its score.

**On the 4B it predicts nothing.** Its four probe-clean functions score the same
as its eleven broken ones. Reading them shows why — these are its *clean* ones:

```python
# qwen3-4b chain 0: a line clear is worth 10; one row of height is worth 5.
score_val = lines_cleared * 10 + (20 - current_height) * 5 \
          + (10 - average_col_height) * 3 - holes * 2
```

```python
# qwen3-4b chain 9: holes weighted 1 against max-height 50, so it buries
# holes to keep the stack flat.
return float(lines_cleared * 100 + (20 - max_col) * 50 + (10 - holes))
```

Neither has a bumpiness term. Both define a hole as a cell walled on all four
sides, which misses nearly every real one. So the 4B fails at **two** levels:
it mostly cannot write valid terms, and when it can, it selects and weights them
incoherently. The probes see the first level only — correctly, since they were
built to test construct validity, not skill. This is the clearest demonstration
so far that "strategy-capable" and "good" are different measurements.

---

## 4. Four rejections, and only one is a coding error

The first functions in the project to be refused before playing. All four are
logged with `played: false` and `invalid_outputs: 1` — **recorded
non-observations, not zeros**, and excluded from score means rather than
averaged in as a false 0.

| rung | chain | cause |
|---|---|---|
| `qwen3-8b` | 4 | syntax error: `if has_filled, below:` |
| `qwen3-8b` | 7 | `import math` |
| `qwen3-14b` | 9 | `import math` |
| `qwen3-14b` | 14 | `import math` |

Three of the four are the AST allowlist refusing an import. That invites the
question of whether the harness is penalising ordinary Python, so the prompt was
checked before any conclusion was drawn. `strategy_v3` says, in bold:

> **No imports.** `math` is already available as a name - use `math.sqrt(...)`
> directly, with no import statement.

These are therefore **instruction-following failures against an explicit,
emphasised instruction**, not setup artefacts — a real measured limitation of
the rung. Both ends of the ladder had zero rejections; only the two middle rungs
produced any.

The design held up exactly as milestone 5 specified: rejected, logged, saved to
disk for inspection, recorded as a failure, no crash, run continued.

### 4.1 Harness-specific conventions caused no errors at all

| probe | failures among the 56 functions that loaded |
|---|---:|
| height | 26/56 |
| holes | 20/56 |
| above-gap | 16/56 |
| **lines** | **0/56** |

`lines_cleared` is the one quantity that is specific to *this* harness — it
arrives in the placement dict rather than being derivable from the board — and
**every function that loaded read it correctly.** Every single defect is board
geometry: row 0 is the top, and the models repeatedly write code that assumes it
is the floor. The benchmark's own conventions are not the difficulty; the
spatial reasoning is.

Per rung, among functions that loaded:

| rung | loaded | height | holes | above-gap |
|---|---:|---:|---:|---:|
| `qwen3-4b` | 15 | 5 | 8 | 3 |
| `qwen3-8b` | 13 | 8 | 4 | 3 |
| `qwen3-14b` | 13 | 10 | 6 | 7 |
| `qwen3-30b-a3b` | 15 | 3 | 2 | 3 |

The 14B's median rate of 1.9 -- below the 4B's 7.4 -- is the same weakness seen
from the other side. As a *rate*, it is the worst rung on height (10/13, 77%) and
above-gap (7/13, 54%), which is the same inversion section 1 found and is not explained by
scale. It is **not** worst on holes: 46% against the 4B's 53%. The failure that
distinguishes this rung is specifically orientation, not defects in general.

---

## 5. The 30B reaches the hand-written baseline cold

`qwen3-30b-a3b` chain 3, iteration 0, no feedback, 22 lines:

```python
def score(board, placement):
    lines = placement["lines_cleared"]
    holes = 0
    for j in range(10):
        has_filled = False
        for i in range(20):
            if board[i][j]:
                has_filled = True
            elif has_filled:
                holes += 1
    top_rows = []
    for j in range(10):
        top_row = 20
        for i in range(20):
            if board[i][j]:
                top_row = i
                break
        top_rows.append(top_row)
    surface_sum = 0
    for j in range(9):
        surface_sum += abs(top_rows[j] - top_rows[j+1])
    return lines * 1000 - holes * 25 - surface_sum * 5
```

Held-out mean **81,300 — 96% of the hand-written heuristic's 84,720**, and that
figure is censored: it hit the 2,000-piece limit in **8 of 10 games**.

| seed | score | pieces | lines | cause |
|---:|---:|---:|---:|---|
| 1000 | 86,700 | 2,000 | 796 | `piece_limit` |
| 1001 | 87,600 | 2,000 | 797 | `piece_limit` |
| 1002 | 87,400 | 2,000 | 798 | `piece_limit` |
| 1003 | 76,500 | 1,787 | 698 | `block_out` |
| 1004 | 86,600 | 2,000 | 795 | `piece_limit` |
| 1005 | 86,800 | 2,000 | 795 | `piece_limit` |
| 1006 | 86,000 | 2,000 | 792 | `piece_limit` |
| 1007 | 87,500 | 2,000 | 798 | `piece_limit` |
| 1008 | 40,100 | 960 | 367 | `block_out` |
| 1009 | 87,800 | 2,000 | 797 | `piece_limit` |

Notable: it carries **no aggregate-height term**. Lines, holes and bumpiness
alone are sufficient — keeping the surface flat and hole-free keeps height down
as a side effect. This is Dellacherie-lite, reproduced cold, one chain in
fifteen, by a 4-bit model on a laptop.

---

## 6. Consequences for the improvement loop

1. **The top rung starts at the ceiling.** A chain censored in 8 of 10 games
   cannot demonstrate improvement, and its total was partly reporting the
   budget. **Done:** the headline is now points per piece, where the best chains
   read 46.4 / 39.0 / 35.1 / 15.6 (top rung to bottom) against the heuristic's
   43.5 -- uncensored, and budget-independent at 43.2-43.5 for the heuristic
   across every budget tried. The switch also changed *which* function looks
   best on this rung: chain 3 wins on totals by surviving longer, chain 4 scores
   faster per piece. That was the fourth time censoring had distorted a result,
   which is why it was fixed rather than noted again.
2. **The loop's premise needs re-scoping.** "Does the loop let a small model
   close on a larger one?" assumes a slope to close. There is no gap between the
   4B, 8B and 14B to close, and the gap to the 30B is a step whose cause is
   confounded. The answerable version: *does the loop move a rung's probe-clean
   fraction?* That is a single number per rung with a known null, and sections 1
   and 3 give the baselines.
3. **Rejections must be reported, not dropped.** Two rungs lost 2/15 chains
   each. Treating those as zeros would have understated the 8B and 14B; dropping
   them silently would overstate their validity rate. Both numbers belong in the
   results table.
4. **The 4B is the wrong rung for loop experiments.** Its score is uncorrelated
   with whether its code works, so no feedback signal derived from score can
   steer it. Any loop result on the 4B measures noise.

---

## 7. Cost

| rung | generations | tokens in | tokens out | generation time | per generation |
|---|---:|---:|---:|---:|---:|
| `qwen3-4b` | 15 | 12,915 | 131,553 | 74.2 min | 297 s |
| `qwen3-8b` | 15 | 12,915 | 136,418 | 139.1 min | 557 s |
| `qwen3-14b` | 15 | 12,915 | 124,161 | 208.1 min | 832 s |
| `qwen3-30b-a3b` | 15 | 12,915 | 148,172 | 86.5 min | 346 s |
| **total** | **60** | **51,660** | **540,304** | **8.5 h** | — |

Dollar cost **$0.00**, as it will be for every planned run. Identical
`tokens_in` across rungs is the byte-identical prompt showing up in the ledger.

Wall-clock was **8.52 h** against 8.46 h of generation, so **generation is 99.4%
of the cost** and the 728 games played are statistically free (~0.3% between
them). Measured per rung: 98.1%, 98.6%, 99.7%, 99.9%. Any future effort to make
a sweep cheaper has to reduce tokens or pick a faster rung; optimising the engine
cannot help, which is consistent with the earlier measurement that generation
could not be sped up here.

---

## 8. Open questions

1. ~~**Raise the piece limit, or switch the headline to points per piece.**~~
   **Done:** the headline is points per piece. The budget still bounds how much
   play any one figure covers -- the best chain's rate rests on ~1,000 pieces
   against the heuristic's 10,467 -- so a longer run would tighten that
   comparison, but nothing is censored any more.
2. **Is the step architectural?** Needs a second MoE or a dense model ≥30B.
   Neither fits this machine, so this may have to stand as a stated confound.
3. ~~**Does the loop move the probe-clean fraction?** The reframed milestone-6
   question, with baselines now measured at 4/15, 5/15, 3/15 and 11/15.~~
   **Answered: no.** Across both completed loops the fraction went from 3/10 at
   iteration 0 to 2/10 at iteration 5 — **1 repair in 40 chances against 2
   regressions**, and on the 4B zero repairs in 20 chances. Revision churns
   individual terms (6 repaired, 7 broken on the 4B) without ever assembling
   all four, because capability is a conjunction. Note the limit: both loops
   are rungs where most first attempts are *already* broken, so this measures
   repair and not refinement — testing refinement needs the 30B, at 11/15. See
   [the-loop-does-not-repair-capability.md](the-loop-does-not-repair-capability.md).
4. **Why is the 14B the worst rung on the orientation probes?** It is below the
   4B on height and above-gap and on overall capability, though not on holes,
   and it is also the slowest. Three separate measurements disfavour this rung
   and none explains it.
5. **Does the `import math` failure persist under a restated prompt?** Three of
   four rejections were one instruction. Whether a rung can follow it is worth
   measuring, but changing the prompt breaks comparability with these 60
   generations, so it needs its own arm.
