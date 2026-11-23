# Finding: prompt v1 vs v2, and a determinism problem

**Date:** 2026-11-19 · **Model:** `qwen3:4b` · **Seed:** 1 · **Temperature:** 0
**Script:** `analysis/compare_prompts.py`
**Artifacts:** `runs/published/qwen3-4b-iter0/qwen3-4b-seed1-strategy_v{1,2}.{py,json}`

Context: [`qwen3-4b-iter0-detailed.md`](qwen3-4b-iter0-detailed.md) recorded a
first run in which the model wrote a constant scoring function. `strategy_v2` was
written in response, adding two mechanical clarifications. This compares them.

---

## 1. Result

| template | score | pieces | holes | moves with variation | mean spread | gen s | out tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| `strategy_v1` | 0 | 22 | 107 | 0/22 | 0 | 252 | 9,020 |
| `strategy_v2` | 0 | 22 | 107 | **4/22** | 0.909 | 276 | 8,333 |

Reference, same seed: heuristic 21,600 · naive 2,100 · random 0.

> **Conditions note.** The `naive` figure comes from an agent that no longer
> exists in the codebase, and the heuristic figure here is at the old 500-piece
> budget (about 21,600 on seed 1) rather than the current 2,000, where the same
> heuristic averages ~84,720. Both conditions are explained in
> [README.md](README.md); ratios quoted against them understate the gap by
> roughly 4x.


**v2 did not fix it.** Score, pieces and final holes are identical. The only
movement is in discrimination: v2's function separates candidates on 4 of 22
moves instead of 0, with a mean spread of 0.909 against a constant term of
roughly 1,960 — far too small to change any decision.

---

## 2. What each wrote

### v1

```python
def score(board, placement):
    filled_cells = sum(cell for row in board for cell in row)
    holes = 200 - filled_cells

    stack_height = -1
    for row in range(19, -1, -1):
        if any(board[row][col] for col in range(10)):
            stack_height = row
            break

    return float(holes * (20 - stack_height) + placement["lines_cleared"])
```

- `holes = 200 - filled_cells` is the count of **all** empty cells. Every piece
  fills exactly four, so this is identical for every candidate of a given move.
- The height loop scans rows 19 → 0 and breaks on the first hit, so
  `stack_height` is the **lowest** occupied row — the bottom of the stack. Once
  anything rests on the floor it is 19, making `(20 - stack_height)` equal 1.
- Net: `constant * 1 + lines_cleared`, and `lines_cleared` never fires. Constant.

Note it *did* add the `break` the previous attempt lacked — then scanned from the
wrong end. Same bug class, different expression.

### v2

```python
def score(board, placement):
    lines_cleared = placement["lines_cleared"]
    empty_cells = 0
    holes = 0
    for row in board:
        for cell in row:
            if not cell:
                empty_cells += 1
    for row in range(20):
        for col in range(10):
            if not board[row][col]:
                up = board[row-1][col] if row > 0 else False
                down = board[row+1][col] if row < 19 else False
                left = board[row][col-1] if col > 0 else False
                right = board[row][col+1] if col < 9 else False
                if up and down and left and right:
                    holes += 1
    return float(lines_cleared * 100 + empty_cells * 10 - holes * 5)
```

- `empty_cells * 10` is again constant per move, and it is the dominant term at
  roughly 1,960.
- `holes` now counts cells **enclosed on all four sides**. A real hole is merely
  *covered from above* — open below is the normal case — so this definition
  almost never matches. Hence 4 moves out of 22 with any variation.
- `- holes * 5` is the only live term, and it is swamped.

---

## 3. Three attempts, three wrong definitions of "hole"

| attempt | prompt | its definition of a hole |
|---|---|---|
| 1 | v1 | all empty cells (`empty_cells`) |
| 2 | v1 | all empty cells (`200 - filled_cells`) |
| 3 | v2 | cells enclosed on all four sides |

The correct notion — an empty cell with a filled cell somewhere **above** it in
the same column — never appeared. All three also got the stack-height direction
wrong, in two different ways.

This is the substantive finding about the bottom rung: the failure is not a
missing instruction. v2 explicitly told the model its scores must differ between
candidates and to check that each term actually varies, and it still produced a
function dominated by a constant term. **The model cannot reliably reason about
whether its own expressions vary with their input.**

---

## 4. The determinism problem

The two v1 runs used a **byte-identical prompt** (SHA256 `2ffd3f79246e72d5`,
2,599 chars) at temperature 0, and produced **different functions**.

The reasoning traces are identical for 7,336 characters, then diverge:

| run | text at the divergence |
|---|---|
| 1 | `...the "tallness" is the lowest row index (highest up) where the col...` |
| 2 | `...the "height" of the column is the lowest row index where it's fil...` |

One word choice, after which they never reconverge. Short generations *are*
reproducible — three identical replies to a one-line prompt, with and without an
explicit `seed` — so this is a property of long generations: with ~9,000 output
tokens, floating-point nondeterminism (non-associative reductions, kernel
scheduling) eventually flips a token, and the rest of the trace follows.

### 4.1 Why this matters more than the prompt result

CLAUDE.md design decision 3 says runs are deterministic and seeded so results
are directly comparable. That holds for the **piece sequence** — three different
generated functions all produced exactly 0 points, 22 pieces and 107 holes,
because all three were effectively constant and therefore played the identical
degenerate game. The engine is provably deterministic.

It does **not** hold for the model. The same prompt does not give the same
function.

The consequence for the headline measurement: an improvement curve built from one
run per iteration cannot distinguish learning from sampling noise. Two of
CLAUDE.md's derived metrics are directly exposed — **regression count** would
count noise as regression, and **iterations to plateau** would be read off a
noisy series.

### 4.2 A fixed seed does not fix it

Tested directly. `seed` **is** honoured by the server: three calls at temperature
1.0 with `seed=42` returned bit-identical text, where three unseeded calls at the
same temperature all differed. So there is a seeded RNG in the sampling path.

But with `seed: 1` and temperature 0, two runs of the *same long prompt* still
produced different functions:

| run | source hash | generation | reasoning |
|---|---|---:|---:|
| 1 | `a617db7ce7bf7e33` | 298s | 34,916 chars |
| 2 | `1ac323317e25d8ee` | 344s | 35,138 chars |

Those two reasoning lengths are exactly the two seen across the earlier unseeded
runs (34,916 and 35,138). The system appears to flip between two trajectories at
an early near-tie, and the seed does not determine which.

**This rules out sampling as the operative cause for long generations.** The
remaining explanation is numerics: floating-point non-associativity in parallel
reductions, kernel selection varying with batch shape or available memory, model
reload between calls (Ollama unloads an idle model after ~5 minutes), or
prompt-cache state. Any of these can shift a logit in its last bits, which is
enough to flip a near-tie — and ours flips on exactly that kind of choice, two
near-synonyms the model has no strong preference between.

An earlier reading of the seed test suggested temperature 0 was simply not
greedy. That was wrong: the seeded test used ~300 output tokens, far too few for
a numerics-driven flip to be likely. Both mechanisms exist; for a 9,000-token
generation, numerics dominates and no seed can remove it.

The seed is kept in the config regardless, since it removes one real source of
variance at no cost. It is simply not sufficient.

### 4.3 But score-level noise may be far smaller than text-level noise

Four generations from this prompt have now produced at least two distinct
functions. Every one scored **exactly 0, at 22 pieces, with 107 holes**.

Token-level nondeterminism did not propagate to the outcome, because both
trajectories produced effectively constant functions, and all constant functions
play the identical degenerate game on a fixed seed.

That matters for how to handle this. The quantity the benchmark reports is the
score, not the text, so **score variance is what has to be measured** — and it
may be much smaller than the generation variance suggests. The catch is that this
particular model is *stably bad*, which is the easiest case. A model producing
functions near some competence threshold could show much larger score variance.
The noise floor therefore has to be measured on a rung that actually produces
varying scores, not on this one.

### 4.3b Measured: token margins, and why the evidence is only partial

Nondeterminism can only surface where the top two candidate tokens are close
enough that a last-bit logit shift flips which is larger. Measured over the first
1,200 tokens of the same `strategy_v2` prompt, with `logprobs`:

| top-1 vs top-2 margin | qwen3:4b | qwen3:14b |
|---|---:|---:|
| < 1e-6 | 0 | 0 |
| < 1e-4 | 0 | 0 |
| < 1e-3 | 1 (0.08%) | 1 (0.08%) |
| < 1e-2 | 6 (0.50%) | 1 (0.08%) |
| < 1e-1 | 44 (3.67%) | 13 (1.09%) |
| **median margin** | **2.09** | **4.39** |

The 14B is clearly the more decisive model: its median margin is 2.1x larger, and
it has 6x fewer tokens under 0.01. That is consistent with it being robust to a
numerical wobble the 4B is not.

**But the measurement does not settle it**, for two reasons worth recording:

1. At the threshold that actually matters -- margins tight enough for
   floating-point noise to flip, plausibly below ~1e-3 -- both models show
   exactly **one** token in 1,200. A sample of one cannot distinguish them.
2. The sample covers the first 1,200 tokens. The 4B's observed divergence
   occurred around character 7,336 of ~35,000, roughly token 1,800-2,000 --
   **just outside the window measured.** The sample does not include the event
   being explained.

So the mechanism is supported directionally and remains the best explanation, but
it is not demonstrated. Resolving it would need margins over the full generations
rather than a prefix.

### 4.3c Consequence: margin screening is not yet a substitute for testing

The appealing shortcut would be to screen a rung by its median margin instead of
running five full generations. On two models with one known outcome each, that
threshold cannot be calibrated. **The honest minimum test for a new rung is to
generate twice and compare hashes** -- about 40 minutes on the 30B, against 90 for
five runs.

### 4.4 What this requires

The noise floor has to be measured before any improvement can be claimed: run
the same model, prompt and seed N times and record the spread of scores. Until
that number exists, there is no threshold against which a gain between
iterations means anything.

~~Options, not yet decided:~~ **Decided: 1 and 2 together, 3 rejected.**

1. ~~**Measure the noise floor in score terms, then require improvements to
   exceed it.**~~ **Done** on two rungs:
   [14B](noise-floor-qwen3-14b.md) and [30B](noise-floor-qwen3-30b.md). The
   prediction held — score variance is far smaller than text variance.
2. ~~**Several samples per iteration, report medians and spread.**~~ **Adopted**,
   as the loop's independent chains: each chain iterates on its own function and
   never sees another's, and `curves.py` reads the curve from the median across
   them. Carrying best-of-N forward would manufacture a curve from noise, so the
   median is the point. `CLAUDE.md` carries the reasoning.
3. ~~**Accept single runs and report the curve as indicative**, with the
   nondeterminism stated as a limitation.~~ **Rejected.** The 30B's 1,700-point
   spread between two runs of the same request is wider than any effect the loop
   has produced, so a single run per iteration cannot be read as a curve at all.

---

## 5. Secondary observations

- v2's prompt is longer (761 input tokens vs 649) and produced slightly *fewer*
  output tokens (8,333 vs 9,020). No evidence the added instructions increased
  deliberation.
- The score-spread diagnostic added after the first run did its job: it
  distinguished "constant function" from "bad strategy" immediately, and showed
  v2's marginal 4/22 improvement that a score of 0 alone would have hidden.
- Generation times were 252s and 276s on the smallest rung. A multi-sample,
  multi-iteration, multi-rung run is a many-hour job and needs checkpointing.

---

## 6. Open decisions

1. How to handle model nondeterminism (§4.2). This gates the validity of the
   headline result and should be settled before Milestone 6 is built.
2. Whether to keep withholding the definition of a hole. Three attempts have now
   failed to derive it. Supplying callable feature helpers would likely produce a
   measurable curve from the 4B rung, at the cost of reducing "improvement" to
   reweighting. The alternative is to accept that the bottom rung may produce a
   flat curve at zero, and report that as the finding.
3. Whether `strategy_v2` should remain the default. It is marginally better on
   discrimination and no worse on outcome, but the difference is within what
   nondeterminism could explain, so the comparison does not justify a preference
   either way.


---

## 7. Addendum: the iteration 0 to 1 confound, and what was fixed (2026-11-20)

A methodology review identified four things changing simultaneously between
iteration 0 and iteration 1, which made the first and largest step of any curve
unattributable. Three are now removed; one is not.

### Fixed: the template changed, not just the feedback

Iteration 0 used `strategy_v2` and later iterations `revise_v1`. Those differed
in several ways at once, and not all in the same direction: `revise_v1` **dropped**
the board-orientation note ("a column is tall when filled cells reach a low row
index") and the placement key table, while adding feedback. Orientation is
precisely what every rung has got wrong, so the prompt change may have hurt at
the same moment the feedback was supposed to help. Net sign unknown.

Now one template (`strategy_v3`) serves every iteration, with a feedback block
that is empty on the first. Verified mechanically: the iteration-0 prompt has
**zero lines absent from the iteration-1 prompt**. The step is a pure insertion
of 54 lines of feedback, and `tests/test_loop.py::TestPromptIsAPureInsertion`
pins it.

### Fixed: the measurement vocabulary appeared for the first time at iteration 1

The feedback reports holes, tallest column and surface unevenness. The 4B's
iteration-0 reasoning trace mentioned surface shape **zero** times (§4.3 of
`qwen3-4b-iter0-detailed.md`), so iteration 1 was handing it a concept it did not
have. That is vocabulary transfer, not learning.

The quantities are now named at iteration 0 as well, so the vocabulary is a
constant treatment rather than a step change. Note what is named and what is not:
the *quantities* are listed, their *definitions* are withheld. A model still has
to work out what a hole is, which is the thing every rung has so far got wrong.
`declare_metrics=False` disables it for an ablation.

Cost of this fix, stated plainly: the observation that the 14B "derived height,
holes and bumpiness unprompted" is no longer reproducible under the default
configuration, because the quantities are now named up front. That finding stands
on its recorded artifacts and the ablation flag, and uniform treatment is worth
more to the headline claim than a clean single data point.

### Fixed indirectly: the floor effect

Score is bounded below at 0 with many observations exactly on the bound, so any
perturbation has non-negative expected change and a curve rising off zero is what
pure noise does. `held-out-seeds.md` establishes `pieces_placed` as the better
curve variable on separate grounds; it also has no pile-up at the floor (22
pieces, not 0).

### NOT fixed: the feedback contains ground-truth labels

The summary pairs the **rendered board** with the engine's **correct hole count**.
That is a labelled (input, label) example for exactly the definition the prompt
refuses to state. A model shown that board and told "96 holes" can in principle
reverse-engineer "covered empty cell" from it.

This cannot be removed without gutting the feedback: dropping the number leaves
the model to count holes on a board it may be miscounting, and dropping the board
removes the most informative signal there is. It is now the **only** thing that
changes at the 0 to 1 step besides the numbers themselves, which is a much
narrower confound than four simultaneous changes.

Consequence for the claim: "the model derived the right features unprompted"
holds at iteration 0 only. From iteration 1 the loop supplies supervision for the
hole concept, and the honest framing of the headline is improvement *given
outcome feedback that includes measured board statistics*, not unaided discovery.
