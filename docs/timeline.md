# Development timeline

How `tetris-bench` was built, and what each stage established. Every figure here
is traceable to a commit or a document in [`findings/`](findings/).

The short version: the engine and baselines took an evening, the model-facing
machinery took a day, and almost everything since has been **measurement** —
establishing what a number from this benchmark is allowed to mean. Seventeen of the
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

> **Later note.** The `naive` row is not reproducible from this repo: no such
> agent exists in the codebase any more, so treat 1,675 as a historical marker.
> The budget also moved to 2,000 pieces, where the heuristic averages ~84,720 on
> held-out seeds. See [docs/findings/README.md](findings/README.md).

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

## 2026-11-21 to 11-23 — the measurement phase

Thirty-four commits, and almost no new capability among them. The build was
finished; what these three days did was establish **what a number from this
benchmark is allowed to mean**, which repeatedly meant withdrawing something
already published here.

### The seed was inert, so five chains were one sample

`87f05e6`, `17730da`. Chains existed so that a rising median across independent
samples could rule out selection bias. At temperature 0 with one model seed,
every chain generated the **byte-identical function** — measured, by hash. A
five-chain run had been four copies of one sample. `model_seed_for(base, chain)`
fixed it, giving chain *k* the seed `base + k` while chain 0 keeps the configured
seed, so a single-chain run stays bit-for-bit what it was. Verified afterwards:
every rung of the ladder produced 15 distinct SHAs across its 15 chains.

### Capability probes, because a low score has two causes

`6e753ab`. A bad strategy and one that *cannot be expressed* both produce a low
number, and the benchmark had no way to tell them apart. The probes separate
them, and the answer reframed the project: **37 of 60 first attempts were broken
rather than bad.**

### The ladder is a step, not a slope

`2ae8c5c`, `41e189b`. All four rungs at iteration 0, 15 chains each, one
byte-identical prompt (SHA `f3a0cb0af765`): 60 generations, 728 games.

| rung | probe-clean | median pts/pc | best pts/pc |
|---|---:|---:|---:|
| `qwen3-4b` | 4/15 | 7.4 | 15.6 |
| `qwen3-8b` | 5/15 | 15.6 | 35.1 |
| `qwen3-14b` | 3/15 | 1.9 | 39.0 |
| `qwen3-30b-a3b` | **11/15** | **26.0** | **46.4** |
| *hand-written heuristic* | — | *43.5* | *43.5* |

4B, 8B and 14B are statistically indistinguishable; the 30B steps up to 11/15,
**p = 0.002** against the three pooled (Fisher exact). So "does the loop let a
small model close on a large one" is ill-posed as written — there is no slope to
close — and it is restated as *does the loop move a rung's probe-clean
fraction?*, which remains open.

The 30B's best function is also the best the project has produced, and it was
the **first thing that chain wrote**: 22 lines, no height term, 96% of the
hand-written heuristic on held-out seeds with no feedback of any kind.

### The headline moved to points per piece

`177d1dd`, `3051399`. A total is censored by the piece budget, and the project's
best function is censored in 8 of 10 games. A rate is not: the heuristic measures
**43.2–43.5 points per piece at 500, 2,000, 20,000 and 50,000 pieces alike**.
Totals stay in the schema and are reported beside the rate, because survival is
a separate thing to know — the clearest case being a function at 92% of the
heuristic's *rate* and 6% of its *survival*.

### The game got its own time bound

`097e36d`, `f45c751`. Bounding the call and the piece does not bound the game. A
function that merely spends its full second on every placement, never looping,
could run 2,000 pieces × 34 placements × 1s — about **19 hours** — entirely
within the rules, and an unattended sweep would simply appear to hang.
`per_game_seconds` closes that, checked between batches rather than inside one,
because cutting a batch short would kill a worker behaving exactly as allowed.

### Two withdrawals, both from measuring the measurement

**The counterexample result was the sampler, not the board.** `05d6df3`,
`6ebf93d`. The published reading — one trace board in three fixes the hole-count
bug — rested on a sweep that **never varied its seed**: consecutive run indices
produced byte-identical output, so what looked like three boards sampled once
each was one board sampled repeatedly. Re-running properly gave 23 outputs and
16 distinct functions, and the board question reopened at **Fisher p = 0.07
one-sided**: suggestive, unsettled. The fire rate was withdrawn outright, being
a rate over floating-point divergence at one fixed seed rather than over seeds.
A regression test now walks `analysis/*.py` and fails if a `.complete()` call
omits its seed.

**The 30B loop is underpowered, not futile.** `ac63400`. The earlier claim was
that the 30B "cannot demonstrate improvement at any affordable sample size".
Both its figures reproduced; the conclusion did not follow. The error was
substituting cross-chain spread (15.13) for the **paired** standard deviation
(8.74, 0.70× of it), which inflated the required sample roughly twofold, and
then treating n=5 as the affordable ceiling. One more chain clears the bar:
**n=6 gives 17.30 against 17.52 of headroom, at 3.5 hours.** The real obstacle
turned out to be effect size — parity with the heuristic needs 1.75× the largest
gain the loop has ever produced — which is a different objection, and the one
that makes the 8B the better next run.

### Milestone 7, measured rather than argued

`04a3160`, `d26e56a`. The direct agent: one model call per piece, the reply an
index into the enumerated legal moves so every option is legal by construction.
One demonstration game, 20 pieces, **3 h 44 m**.

**672 s and 6,444 output tokens per piece** — 64× strategy mode charged against
a single game, 822× amortised over the ~900 pieces a function is actually
replayed across. A full 2,000-piece game would be 15.4 days, which is why this is
a demonstration and not a rung.

It also scored 0 with **86 holes**, against random play's 70.6 over 200 agent
seeds on the same sequence — the 80th percentile, inside the distribution. With
**0 malformed replies in 20 calls**, so the failure is choice and not formatting,
which is exactly what the index design was built to isolate.

*582 → 698 tests.*

---

## 2026-11-23 (evening) — the second rung

The 4B loop: 5 chains, 6 iterations, 2 h 22 m, 30 generations, 243,280 output
tokens. Run because every claim this project made about what the loop *does*
rested on the 14B alone, and because the 4B is the cheapest rung that could test
it. Same seed splits as the 14B five-chain run, so the curves compare directly.

**The median curve fell**, 7.49 → 3.72 points per piece, with three of five
chains ending below where they started. Nothing is detectable either way: the
measured paired standard deviation is 8.69, so five chains see only changes
above 10.88. The starting point replicates the ladder's independent 15-chain
median of 7.36, so the shape is not a sampling accident.

**Chain 3 is the result.** Its first revision wrote
`total_empty = total_empty(board)` — shadowing the function it calls, so every
scoring call raised `UnboundLocalError` and the game recorded 342 sandbox
failures. It then carried that line **verbatim through five consecutive
revisions**, retuning the coefficients around it each time, while the revise
prompt quoted the interpreter's error back to it three times naming the
variable. The existing "first revision reweights instead of debugging" finding
was about a semantic bug under outcome-only feedback, where "it was never told"
is a defence. This one had the traceback.

**And the probes say the loop did not repair capability either**, which closes
the question the ladder restated. The strategy-capable fraction sat at 1/5 at
every one of the six iterations: **0 repairs in 20 chances, 0 regressions.** The
14B's own loop manages 1 repair in 20 against 2 regressions, so pooled it is 1
in 40 against 2 — the fraction ends lower than it starts. Revision does move
individual terms, 6 repaired and 7 broken on the 4B, but capability is a
conjunction over terms and fixing them one at a time while breaking others does
not arrive. This was the last remaining way the loop could have been doing
something the scores could not see.

**And the zeros rate is null too, with the power calculation that explains the
silence.** Pooled over both loops: 5 revivals against 5 deaths over 50
transitions, exact sign test **p = 1.000**, with "dead" drawn at a measured line
— the 95th percentile of what random play itself scores over a 10-game
evaluation, 0.851 points per piece. The useful part is the sample size: power is
spent on pairs that *change state* and only 10 of 50 did, so the test needs
**15-55 chains** against the 5 that ran. Four write-ups had deferred this
question; the answer is that the design could not have detected it. That makes
three independent checks for an effect the curve cannot see — the mean,
function-level capability, and the dead-function proportion — all null.

**It also broke a power assumption of the project's own**, and the one used to
justify this very run. The 4B's paired standard deviation came out **2.39× its
cross-chain spread**, where the 14B's is **0.70×** — the opposite direction. The
prediction had been n=1.2 chains to detect a +8.04 gain; the measured figure is
n=9.2. Low cross-chain spread on this rung measured a floor effect, not
stability: a single revision moves a chain from 8.35 to 0.27 and back to 10.47,
so iterations within a 4B chain share no stable lineage. The 30B's published
14-chain requirement scales from the 14B's ratio and is now a lower bound.

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
| A per-chain seed makes chains independent | Not at temperature 0, where it is inert: five chains generated one byte-identical function. Independence needed `model_seed_for`, and was verified by hash afterwards | `87f05e6`, `17730da` |
| A counterexample fixes the bug on one trace board in three | The sweep never varied its seed, so that was one board sampled repeatedly, not three sampled once each. Re-run properly: 23 outputs, 16 distinct functions, board question reopened at Fisher p = 0.07 one-sided | `6ebf93d`, `05d6df3` |
| The counterexample arm's "fire rate" | A rate over floating-point divergence at one fixed seed, not over seeds. Withdrawn outright | `6ebf93d` |
| The 30B loop cannot demonstrate improvement at any affordable sample size | Both figures reproduced, the conclusion did not follow: cross-chain spread was substituted for the paired standard deviation (0.70× of it), and n=5 treated as the ceiling. n=6 clears the bar at 3.5 hours | `ac63400` |
| Total score is the headline | Censored by the piece budget, and the best function is censored in 8 of 10 games. Points per piece is budget-independent: 43.2–43.5 for the heuristic at 500, 2,000, 20,000 and 50,000 pieces | `177d1dd` |
| Per-piece latency grows as the board fills | Three samples against twenty. Over a full 20-piece game the second half averaged 577 s against the first half's 754 s, r(index, latency) = −0.279 | `d26e56a` |
| Paired σ_d is about 0.70× cross-chain spread, so cross-chain spread is the safe proxy | A property of the 14B, not the method. On the 4B it inverts to 2.39×, because a single revision there replaces or breaks the function rather than refining it. Predicted n=1.2 chains for a +8.04 gain, measured n=9.2 | 2026-11-23 |
| The 4B is cheap to measure through the loop because it is the quietest rung | Quiet at iteration 0 was a floor effect — every chain starts near-equally bad — and said nothing about how violently a chain moves once revisions start | 2026-11-23 |

---

## Where it stands

**Every milestone is built and tested, under 698 unit tests.** Milestone 7, the
direct agent, landed as a single demonstration game rather than a full arm,
because 672 s per piece makes a powered version weeks of wall clock for a
baseline whose purpose is to be beaten; the cost ratio was its deliverable and
it is measured.

What remains is measurement. **Two rungs have now been through the loop** — the
14B, whose median rose +8 inside a noise bar of 13, and the 4B, whose median
fell 3.77 inside a noise bar of 10.88. Neither shows a detectable change, which
is a firmer version of the headline than one rung could support, but the 4B
cannot distinguish "the loop does nothing" from "the 4B has nowhere to go": its
honest headroom is 8.27 points against a 10.88 threshold.

**The 8B at 10 chains, ~9.3 hours, is the run that would settle it** — the rung
with both room (27.87 points) and the project's best headroom-to-noise ratio,
2.29 against the 30B's 1.31. The rest of the outstanding list is in the README's
[Not done](../README.md#not-done).

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

1. ~~**A per-chain model seed,** so chains are independent without abandoning
   reproducibility, followed by a multi-chain curve on this rung.~~ **Done.**
   `model_seed_for(base, chain)` gives chain *k* the seed `base + k`, and chain 0
   keeps the configured seed so a single-chain run stays bit-for-bit what it was.
   Verified independent: every rung of the ladder produced 15 distinct function
   SHAs across its 15 chains. The multi-chain curve followed on the 14B.
2. **Is the frequency penalty harmful?** It was added to fix a non-terminating
   generation, which it did decisively. It also appears to have changed what the
   model writes, on the one comparison available. Needs several samples per arm.
3. ~~**Raise the piece budget.** Iteration 4 is censored at 500 pieces on half
   its sequences, so the ceiling is now the measurement rather than the model.~~
   **Resolved by changing the measure, not the budget.** The default moved to
   2,000, but the ladder's best function is censored in 8 of 10 games there too,
   so raising it only moves the hazard up the scale. The headline is now points
   per piece, which has no such failure mode — 43.2-43.5 for the heuristic at
   500, 2,000, 20,000 and 50,000 pieces alike. The budget still bounds how much
   play any one figure covers, which is a limit on precision rather than a
   censored measurement.
4. ~~**The ladder.** 4B, 8B and 30B under the same protocol, and whether the loop
   lets a smaller rung close on a larger one.~~ **Answered** for iteration 0, all
   four rungs, 15 chains each: [size-ladder-is-a-step.md](findings/size-ladder-is-a-step.md).
   There is no slope to close — 4B, 8B and 14B are statistically
   indistinguishable (3–5/15 probe-clean) and the 30B-a3b steps up to 11/15
   (p = 0.002 against the three pooled). The second half of the question is
   therefore ill-posed as written and is restated there as *does the loop move a
   rung's probe-clean fraction?*
5. **Credit assignment.** Still the project's most interesting result and its
   least replicated, but the earlier description of it — *three boards, one
   success* — was withdrawn: the sweep never varied its seed, so that was one
   board sampled repeatedly. Re-run properly it gave 23 outputs and 16 distinct
   functions, and **which board works is reopened at Fisher p = 0.07
   one-sided**. One rung, one iteration, and now an honest p-value instead of a
   ratio. See
   [counterexample-is-the-sampler-not-the-board.md](findings/counterexample-is-the-sampler-not-the-board.md).
6. **The loop on a second rung.** Added here because it is now the top of the
   list: every statement this project makes about what the loop *does* rests on
   the 14B alone. The 8B at 10 chains, ~9.3 hours, is the run that turns one
   rung's behaviour into a measurement.
