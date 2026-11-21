# Development timeline

How `tetris-bench` was built, and what each stage established. Every figure here
is traceable to a commit or a document in [`findings/`](findings/).

The short version: the engine and baselines took an evening, the model-facing
machinery took a day, and almost everything since has been **measurement** —
establishing what a number from this benchmark is allowed to mean. Four of the
project's own published results have been corrected by later measurement, and
that thread is tracked separately in [Corrections](#corrections) below, because
it is the part a reader should trust least on first reading and most on
reflection.

---

## 2026-11-18 — the engine, in one evening

Three milestones, committed within 46 minutes of each other.

**`ad52207` Milestone 1 — the engine.** Board, pieces, rotations, collision,
line clears, a seeded 7-bag randomiser, legal-placement enumeration, game-over
detection. No LLM code anywhere near it, and that separation has held since.

**`9b6e93a` Milestone 2 — baselines.** A random agent and a hand-written
heuristic, which exist to sanity-check the engine and to give the ladder a
ceiling. The design decision that paid off later: the **scoring function** is
the primitive, not the agent. `ScoringFunction` is `(board, placement) -> float`
and `ScoringAgent` applies one to every legal placement — the exact signature a
model would later be asked to produce, so a sandboxed model-written scorer slots
in beside the hand-written one with no parallel code path.

Reference scores at the 500-piece budget, mean over seeds 1/2/17/123:

| agent | score |
|---|---:|
| random | 0 |
| naive | 1,675 |
| heuristic | 21,450 |

The heuristic hits the piece cap on every seed with 1–5 holes, so the budget
bounds it rather than its skill.

Two subtler choices. The random agent owns its own RNG, because sharing the
game's piece RNG would let agent draws shift the piece sequence — two agents
would face different games and the premise that every model plays identical
seeds would fail *silently*. And `apply_placement()` was extracted so the engine
and any scoring function share one definition of committing a move.

**`56aff02` Milestone 3 — rendering and records.** The whole model-facing surface
in one file, so it is reviewable in one place. Filled cells render as `#` rather
than the piece letter, because Tetris is Markovian in occupancy: which piece
filled a cell cannot change the best move. A column index row sits above the
grid so a model reads the column off the board instead of counting cells.

Records are layered — `GameResult` knows nothing about models, so the baseline
agents emit complete records with no empty fields, and `RunRecord` wraps one with
model, mode, iteration and a usage tally. JSONL rather than a JSON array, so a
run that crashes leaves every completed game readable on disk.

*213 → 267 tests.*

---

## 2026-11-19 — the model client, the sandbox, and the first uncomfortable results

**`8df38f0` Milestone 4 — one client for every provider,** and a scope change
that reshaped the project.

The client is deliberately boring: known providers supply their base URL and key
environment variable, pricing lives in config so a cost logged months ago stays
explainable by the file that produced it, and the transport is a one-method
protocol so every test runs with no network, no API key and no local model. That
last point matters more than it looks — the code that records failures has to be
exercised on purpose, not when a provider happens to be down.

**The scope change: local-only, no paid APIs.** The secondary angle became a
capability ladder across one model family at increasing sizes (4B to 30B), asking
whether the improvement loop lets a small model close on a larger one. That is a
sharper question than beating a model costing orders of magnitude more. The
consequence: dollar cost is always zero, so the headline cost measures are
**tokens and wall-clock seconds**. `estimated_cost_usd` stays in the schema so a
paid model could be added without a migration.

**`b995720` Milestone 5 — the sandbox and the strategy agent.** Two independent
safety layers: a static AST allowlist that rejects imports, private and dunder
attribute access, and the builtins that reach outside the process; and
containment in a separate interpreter under `-I` with a small builtins allowlist
and `SIGALRM` bounding each call. Verified to hold *with layer 1 disabled* —
`open` and `__import__` are `NameError`s, `import` fails at load, boards are
immutable tuples, non-numeric and `NaN` returns are refused.

One worker per game, batched per piece, because a game is ~500 pieces × ~34
placements: a process per scoring call would mean 17,000 spawns and over eight
minutes per game of pure process creation.

The validation that mattered: the reference weights expressed through the
plain-data sandbox API score **byte-identically** to the in-process heuristic
(21,600 / 21,200 on seeds 1 / 2). So the API can express a strong strategy and
the sandbox adds no distortion — any shortfall is the model's.

Then it was actually run, and the first findings are all negative:

- **`qwen3-4b` wrote a constant scoring function.** Valid, safe, non-crashing
  code returning the same score for every candidate — one distinct value across
  all 17. The agent degenerated into playing the first legal placement and scored
  0.
- **That failure was invisible.** The harness reported zero sandbox failures,
  which was true and useless. `StrategyDiagnostics` now records whether a
  function separated its candidates at all (0/22 moves with variation, against
  the reference's 500/500).
- **A better prompt did not fix it.** `strategy_v2` added two mechanical
  clarifications: identical score, discrimination rising only 0/22 to 4/22. Three
  attempts produced three different wrong definitions of "hole". The failure is
  not a missing instruction.
- **Generation is not reproducible on `qwen3-4b`,** even at temperature 0 with a
  fixed seed — a byte-identical prompt produced different functions, diverging
  ~7,300 characters in on one near-synonym. The seed *is* honoured (proven at
  temperature 1.0), so sampling is not the cause; floating-point
  non-associativity in parallel GPU reductions is, and no seed removes it.
- **`qwen3-14b`, by contrast, was fully reproducible** — five identical requests,
  one byte-identical function. **Determinism is model-specific and must be
  checked per rung.**

*353 → 449 tests.*

---

## 2026-11-20 — the loop, and four days of methodology in one

**`236a8c7` Milestone 6 — the improvement loop,** the project's differentiator,
plus a three-agent review of it.

The design commitments, each guarding against a specific way to manufacture a
result:

- **Independent chains.** Each iterates on its own function and never sees
  another's, so a rising median across chains cannot be selection bias. Carrying
  best-of-N forward would manufacture a curve from noise.
- **Feedback is symptoms, not diagnoses** — score, lines, holes, height, cause of
  death, board snapshots, the prior function. The model must diagnose its own
  bug, because that is the ability being measured.
- **Resumable by replay, no state file.** Records append as games finish and
  functions are written to disk; a rerun reads the log and replays the saved
  function to regenerate its feedback in under a second. One source of truth
  instead of a checkpoint that can drift. This decision later rescued two entire
  runs.

Six review fixes landed with it, each verified by reproducing the failure first.
The sharpest: a model function containing a broad `except Exception:` inside a
loop could **swallow the sandbox's own `SIGALRM` timeout**. `setitimer` is
one-shot, so no second alarm fired, the worker wedged, and the crash would have
aborted a multi-hour sweep. `CallTimeout` now derives from `BaseException` so
model code cannot catch it.

**`f840a10` — removing the iteration 0→1 confound.** A methodology review found
**four things changing simultaneously** between iteration 0 and iteration 1,
making the first and largest step of any improvement curve unattributable. Three
were removed. The worst was that the *template* changed, not just the feedback —
and `revise_v1` had **dropped** the board-orientation note while adding feedback.
Orientation is precisely what every rung got wrong, so the prompt change may have
been hurting at the same moment the feedback was meant to help. `strategy_v3` now
serves every iteration, with an empty feedback block on the first, pinned by a
test asserting the step is a pure insertion.

The cost was stated plainly rather than buried: the observation that the 14B
"derived height, holes and bumpiness unprompted" is **no longer reproducible**
under the default config, because the measurement vocabulary is now declared at
iteration 0 too. Uniform treatment was judged worth more than one clean data
point.

**`3f263f5` Phase 1c — holding evaluation seeds out.** The loop had been feeding
each chain its own seed's outcomes, so every sequence was a training sequence and
nothing was held out. A position became a `(chain, iteration)` rather than a
`(seed, chain, iteration)`: it plays every training sequence, feedback aggregates
across them, and the function is then replayed on a **disjoint** set of evaluation
sequences the model never sees. The curve is read from those rows. Evaluation
costs under a second per game, so this is free.

**`51bc07e` — the first revision reweighted instead of debugging.** The project's
first evidence on its own headline question, and it is negative. Iteration 0's
function had an identified defect: a hole count flagging cells near the *top* of
the board rather than beneath the stack. The feedback told it the game ended with
96 holes. Two independent revisions kept that line **character-for-character** and
changed only the weights:

```
iteration 0   lines * 10  - max_height      - holes      - bumpiness * 0.5
revision A    lines * 100 - max_height * 10 - holes * 5   - bumpiness * 2
revision B    lines * 100 - max_height * 5  - holes * 10  - bumpiness * 2
```

Told "96 holes", the model concluded "penalise holes more" rather than "my hole
count may be wrong". Held-out: 110 → 130 and 85, flat.

This promoted the counterexample arm to the top of the backlog.

**`997b367` — a feature-level counterexample fixed what outcome feedback could
not.** Identical outcome feedback plus one block: for a single mid-game board,
the true per-column heights and the true hole count.

| arm | held-out | pieces | holes | the bug |
|---|---:|---:|---:|---|
| iteration 0 | 110 ± 107 | 29.1 | 85.8 | present |
| control A | 130 ± 108 | 30.6 | 82.2 | untouched |
| control B | 85 ± 81 | 27.8 | 88.0 | untouched |
| counterexample | **2,540 ± 1,060** | 101.5 | 28.7 | **fixed** |
| reference | 20,915 ± 1,563 | 494.2 | 5.7 | — |

The surprise: the trace block contained prose *defining* column height plus the
labelled heights array, and the model kept its broken fill-count heights anyway.
So the bug it fixed was given as a bare number with no definition; the bug it did
not fix was given as a definition plus labelled data — backwards from what one
would predict. That matters for attribution, because the obvious objection to
this arm is that the trace smuggles in a definition. The data does not support
that: the handed-over definition went unused.

**What it supports:** the bottleneck is **credit assignment, not capability**.
The 14B could fix this all along; "you finished with 96 holes" does not localise
the fault, because that number is equally consistent with a correct hole count
and a bad weight — the reading both controls took.

**`2ed3e85` — replication.** Three runs; two byte-identical (so one sample), the
third a genuinely different generation whose four weights were scaled by exactly
10×. Uniform positive scaling cannot change an argmax, verified rather than
assumed: across all 17 candidates the score ratio is exactly 10.0 and both choose
the same placement. So: two independent generations, both deriving the correct
hole count and the same relative weighting, against two controls that left the
bug untouched.

*502 → 519 tests.*

---

## 2026-11-21 — board variation, the analysis layer, and two infrastructure bugs

Six commits: `45461fe` `cb72505` `8550a52` `276cedd` `8ce19dc` `9f3d558`,
plus the one that added this file. ~3,050 new lines across seven files and ~680
changed. (A commit cannot cite its own hash, which is why the seventh is named
rather than numbered.)

**Board variation refuted the headline.** `2ed3e85` had recorded the remaining
weakness itself: all three replication runs used the identical prompt, so they
probed generation variance rather than robustness to *which board* the trace
shows. Varying it costs the same. Result: of three trace boards, **one** produced
a correct hole count (5 holes, matching the engine), one kept the bug verbatim
(120), and one produced a *new, inverted* bug (173 against the engine's 5 — which
a string-matching detector initially scored as a fix, a false positive caught by
measuring against `metrics.holes`). Prompts were within 10 characters, so length
explains nothing. The finding's title now ends "— on one trace board in three".

**Milestone 8, the analysis layer, built before the run it would read.** Pure,
stdlib-only aggregation in `curves.py` with presentation split out, so a change
to how a number is displayed cannot change the number. Four choices are recorded
in its docstring because each could manufacture a result: the curve is read from
eval rows; deltas are paired within a chain; chains combine by median; generation
cost lives on training rows only.

Building it first caught two traps that would each have cost a rerun. **The
"net delta per revision" row was a telescoping sum** — algebraically
`(last − first)/steps`, carrying no information beyond first-to-last, while
reading like a per-step average. And a chain gaining 0.1 points produced
"312,000 tokens per point", so cost-per-point is now gated on the noise bar and
reports *undefined* otherwise. The verdict line was also changed to report a
**margin** rather than a threshold crossing, after a no-trend control arm crossed
the bar at 1.7×.

**Two infrastructure bugs, both found the expensive way.**

`ord` was missing from the sandbox's builtins allowlist. A model used
`ord(placement["kind"])` as a tie-breaker — a reasonable thing to write — and
every scoring call raised `NameError`: 4,495 sandbox failures per position, with
four iterations of a six-iteration run collapsing from a held-out 1,580 to 10.
The run was recovered in 4.3 seconds by replaying saved artifacts, which is the
replay-based resume design earning its keep. Comparing hashes afterwards made it
a controlled experiment: iteration 2's function is **byte-identical** across the
two runs and scored 10 before and 990 after, isolating the collapse to the
missing builtin with no ambiguity. An omission in that allowlist does not fail
safe — it fails as a plausible-looking strategy that cannot play.

Then iteration 4 **would not terminate**: three attempts (1200s, 1200s, 2400s),
80 minutes of GPU, nothing logged. Raising the timeout changed nothing because
the generation was not slow, it was non-halting. Ollama's sampler configuration
explained it — greedy decoding (`temp = 0`) with every anti-repetition mechanism
disabled (`repeat_penalty = 1.0`, `dry_multiplier = 0.0`). In that configuration
a reasoning loop is **absorbing**: the next token is a deterministic function of
the context, so once the trace re-enters a state it has visited it cycles forever.
Repetition in iteration 3's trace had already reached 24.6% duplicated 12-grams.

This is a real tension in the design rather than a simple bug: **temperature 0 is
in the project for reproducibility, and it is also what makes the failure
permanent.** The fix keeps both properties — a `frequency_penalty` leaves decoding
deterministic while making repeated tokens progressively less attractive. On the
byte-identical prompt, 22,223 tokens and no termination became **7,152 tokens in
433 seconds**, with repetition down to 2.7%.

**The first clean six-iteration curve**, every point generated under one config:

| iter | held-out | median | train | pieces | holes |
|---:|---:|---:|---:|---:|---:|
| 0 | 20 | 0 | 0 | 15.0 | 137.2 |
| 1 | 2,290 | 1,950 | 1,533 | 98.0 | 26.9 |
| 2 | 2,130 | 2,050 | 1,700 | 93.2 | 27.5 |
| 3 | 470 | 500 | 600 | 52.2 | 31.2 |
| 4 | **14,860** | 19,500 | 19,333 | **378.0** | 16.4 |
| 5 | 6,850 | 7,000 | 2,100 | 184.8 | 27.0 |

Iteration 4 is the best model-written function this project has produced, by
roughly 6×, and it is a **lower bound**: it reached the 500-piece budget on five
of ten held-out sequences, so the budget bounds it rather than the function, the
same way it bounds the reference heuristic. Against that reference — 20,915 and
494 pieces — a model-written scorer is now within striking distance.

The lineage around the peak is the clearest credit-assignment failure the project
has recorded, and it needs the code to see:

- By **iteration 3** the hole count was correct, but `heights[col]` held the *row
  index* of the topmost filled cell — inverted, since row 0 is the top. Its score
  subtracted those terms, so it penalised low stacks. 470.
- **Iteration 4** flipped those two signs to `+`. Given the inverted metric, that
  is the behaviourally correct move: rewarding a large row index rewards a low
  stack. It did not touch the definition. **14,860.**
- **Iteration 5** then "fixed" the definition — `height += 1` counting filled
  cells from row 0 with a `break` on the first empty one — and flipped the signs
  back to `−`. Row 0 is empty on any live board, so that loop returns **zero for
  every column**, making `aggregate_height`, `max_height` and `bumpiness`
  identically zero. Three of five terms died, the function reduced to
  `lines*1000 − holes*50`, and it blocked out on all ten sequences. 6,850.

So the model's best function was conceptually wrong and behaviourally right, and
correcting the concept destroyed the behaviour.

*519 → 582 tests.*

---

## Corrections

Published results this project has overturned with its own later measurement.
Listed because the pattern — measure, then measure the measurement — is the main
methodological claim being made.

| what was claimed | what later measurement showed | where |
|---|---|---|
| A fixed seed makes generation reproducible | Not on `qwen3-4b`; reproducibility is a property of the (model, prompt) pair and must be measured per rung | `b995720`, `51bc07e` |
| The 30B's run "scored 0" | Held-out mean 325, reaching 1,600 — mediocre, not dead. Seed 1 was simply a sequence it could not clear a line on | `236a8c7` |
| The 14B's function scored 400 | That was its luckiest sequence of twenty-one. Held-out mean 110 | `236a8c7` |
| `score` is the curve variable | `pieces_placed` separates functions 1.9× better relative to seed noise (variance ratio 2.07 vs 1.10); `score` is driven by rare multi-line clears and has a dead zone at 0 | `236a8c7` |
| The heuristic weights are El-Tetris's | They are Yiyuan Lee's 2013 genetic-algorithm values; El-Tetris is a different algorithm with six different features | `f840a10` |
| The 14B derived height, holes and bumpiness unprompted | No longer reproducible once the measurement vocabulary is declared uniformly at iteration 0 | `f840a10` |
| An unparseable reply no longer clobbers the chain's previous function | Only the logging half had landed; a probe confirmed the empty code block was still reaching the next prompt. The earlier commit message overstated its own fix | `3f263f5` |
| A counterexample trace fixes the hole-count bug | On one trace board in three. Another kept the bug verbatim; a third produced a new inverted one | 2026-11-21 |
| The 23× counterexample improvement, measured against a 110 baseline | That baseline is `strategy_v2`. On `strategy_v3`, iteration 0 scores a held-out 1,580 unaided, so on pieces the advantage is 101.5 vs 71.8 — ~1.4×, not 23× | 2026-11-21 |

---

## Where it stands

Milestones 1–6 and 8 are built and tested. Milestone 7 (the direct agent) is
not started.

There is now one clean six-iteration curve, and it is simultaneously the
project's strongest result and its least trustworthy. `curves.py` reports the
gain as `+6,830, which is 21.5x the noise bar of 318`. Three reasons not to quote
that number:

- **The bar excludes generation noise.** 318 is seed noise on a ten-game mean.
  Direct evidence that generation noise dwarfs it: the two runs' iteration 0 used
  a byte-identical prompt and the same model seed, differing only in the sampler,
  and scored **1,580 and 20**.
- **The baseline collapsed.** Iteration 0 scored 20 because that generation
  reproduced the inverted-orientation bug. A gain measured up from 20 is not the
  same claim as one measured up from 1,580, and the choice between them was not
  made by the loop.
- **The steps are enormous.** Typical step size 2,270 across five steps. A random
  walk with that step size will often end higher than it started and will often
  have a high interior peak, which is exactly the shape observed.

The unavoidable methodological problem: **chains cannot fix this on this rung.**
Chains were introduced so a rising median across independent samples could rule
out selection bias, but at temperature 0 with one model seed every chain
generates the identical function — measured, byte-identical hashes. Independent
samples therefore require a **per-chain model seed**, which the loop does not yet
support. That is the next change, and nothing about the headline is quotable
before it lands.

Open questions, in rough priority order:

1. **A per-chain model seed,** so chains are independent without abandoning
   reproducibility, followed by a multi-chain curve on this rung.
2. **Is the frequency penalty harmful?** It was added to fix a non-terminating
   generation, which it did decisively. It also appears to have changed what the
   model writes, on the one comparison available. Needs several samples per arm.
3. **Raise the piece budget.** Iteration 4 is censored at 500 pieces on half its
   sequences, so the ceiling is now the measurement rather than the model.
4. **The ladder.** 4B, 8B and 30B under the same protocol, and whether the loop
   lets a smaller rung close on a larger one.
5. **Credit assignment.** The counterexample arm is the project's most
   interesting result and its least replicated — one rung, one iteration, three
   boards, one success.
