# Development timeline

How `tetris-bench` was built, and what each stage established. Every figure here
is traceable to a commit or a document in [`findings/`](findings/).

The short version: the engine and baselines took an evening, the model-facing
machinery took a day, and almost everything since has been **measurement** —
establishing what a number from this benchmark is allowed to mean. Twenty-eight of the
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

**And the `import math` rate was quantified against the right denominator.**
Three of the project's four rejections were that one instruction, which as "3 of
60 ladder generations" reads as a 5% nuisance. But 55 of those 60 never wanted
`math`. Five functions in the whole 131-generation corpus reach for it, all five
want `math.sqrt` — the call the prompt's own worked example names — and **three
of the five imported it anyway**. The two that did not are what make this a
capability result rather than a broken facility. Revisions never do it, 0 of 55,
and not because the revise prompt states the rule better: it states it worse,
unbolded and without an example. The likelier reason is that a revision carries
the model's own import-free function as a template.

**And the discriminate warning does not fix inert arithmetic.** Of 134
published generations, **132 received the warning and 2 did not**, so the
comparison that question wanted was never available. What is measurable: five of
125 functions are inert on every one of eight probe boards, all five on the 4B,
and **three of the five were written under the warning**. In the single
controlled v1/v2 pair both members are inert. The 30B produces no flatness
anywhere. The transferable part is a measurement trap — a one-board probe
over-reports flatness about five-fold, because on a near-empty board many
placements are genuinely equivalent and a *correct* function scores them alike.

**It also broke a power assumption of the project's own**, and the one used to
justify this very run. The 4B's paired standard deviation came out **2.39× its
cross-chain spread**, where the 14B's is **0.70×** — the opposite direction. The
prediction had been n=1.2 chains to detect a +8.04 gain; the measured figure is
n=9.2. Low cross-chain spread on this rung measured a floor effect, not
stability: a single revision moves a chain from 8.35 to 0.27 and back to 10.47,
so iterations within a 4B chain share no stable lineage. The 30B's published
14-chain requirement scales from the 14B's ratio and is now a lower bound.

---

## 2026-11-24 — the third rung, and a power figure retired

The 30B pilot: 6 chains, 6 iterations, 3 h 42 m, 36 generations, 337,273 output
tokens. Run as a **power pilot** rather than as an attempt to show improvement.
Every power claim in the repo had been scaling its paired standard deviation
from the 14B, and the 4B had just shown that the scaling can invert; the pilot's
job was to measure the 30B's term directly.

**It did, and the published figure did not survive.** Measured σ_d is **16.76**
against the **10.54** scaled, too low by 1.59×, which turns a published
requirement of "14–28 chains" into **34**. With three rungs now measured the
ratios to their own cross-chain spreads are 0.70× (14B), 1.05× (30B) and 2.39×
(4B) — a 3.4× span with no constant in it. The scaling method is retired rather
than adjusted: a power claim in this project measures its own paired term or
says out loud that it is extrapolating.

**The curve itself is the third null.** Median gain +7.37 against a minimum
detectable 19.16. It is also the first run where the loop had working functions
to refine — the 30B starts 4 of 6 probe-clean where the other rungs start mostly
broken — and it ends 4 of 6, with 3 repairs against 3 regressions.

**And it overturned a headline.** The project's best function had been a 46.4
first attempt, which supported the uncomfortable claim that the best result
needed no feedback at all. The pilot's chain 1 reached **50.19 points per piece
at iteration 5**, over about 18,000 held-out pieces, by raising its hole penalty
from 20 to 350 and dropping its line reward from 100 to 10 across five steps —
the project's only clean example of a revision getting a weighting right. The
claim is withdrawn. What replaces it is weaker rather than stronger: +8.64 sits
well inside this rung's 16.76, so the loop produced the best function without
being shown to be the reason.

**The counter-example is in the same run.** Chain 2 inverted one sign at
iteration 3 — `+ sum_tops` to `- sum_tops`, on a board where row 0 is the top,
so the term now rewarded building tall — kept it through two more revisions, and
declined at every step: 24,710 → 11,470 → 5,810 → 1,860 → 820. The same
inversion sits inside chain 0's iteration 5, the project's *second*-best
function, where it is harmless because a line clear is worth 3,000 and a hole
200. So the bug is not what separates the best chain from the worst; the scale
of the terms around it is.

One generation produced nothing: 14,000 output tokens, exactly `max_tokens`,
still writing. The project's fifth rejection and its first **length cap** rather
than a rule violation — which means the import-rule write-up was counting one
phenomenon where there are two. The chain's lineage survived it, because the
loop keeps the last function that played rather than carrying an empty source
forward.

The 8B loop — 10 chains, the run that could still move a headline — started at
01:42 UTC the same night.

---

## 2026-11-24 (morning) — the fourth rung, and revisions that change nothing

The 8B loop took the GPU 27 seconds after the 30B pilot released it — Ollama
serves one model at a time, so the launcher waited on the pilot's pid rather
than on a person — and ran 10 chains × 6 iterations in 7 h 09 m for 60
generations and zero dollars. **The last rung, and the largest run in the
project.**

### A fourth null, and the first one worth quoting a bound from

Median gain **+2.51** against a minimum detectable gain of **11.02**; seven
chains up, three down, sign test p = 0.344. What ten chains buy is not a
different answer but a usable one: an 8B improvement of eleven points per piece
or more is ruled out, and a gain of five is not addressed. Resolving the +2.51
would take **193 chains**; resolving a +5 would take 49, about six hours. Every
other rung is several times dearer for the same resolution, which makes the 8B
the only place an adequately powered curve is affordable.

All four rungs now carry a **measured** paired σ_d — 8.69, 12.44, 8.74, 16.76 —
so nothing in the repo scales one from another any more. Their ratios to their
own cross-chain spreads are 2.39×, 0.84×, 0.70× and 1.07×. Recomputing all
four with one piece of code also turned up that the published ratios had been
using **two different denominators**: the 30B's 1.05× came from the standard
deviation of the iteration-0 rates, the 4B's and the 14B's from
`Curve.chain_spread()`. Same conclusion either way, and a reminder that a
cross-run comparison is only as good as its definitions.

### The result the curve could not have shown

Chain 1's final revision rewrote its scoring function and then scored
**identically on all thirteen sequences, game for game, piece for piece**. Every
weight had been doubled, and doubling every weight of a linear score cannot move
its argmax. Not an unlucky revision — one incapable of choosing differently,
for 428 seconds of inference.

Counting adjacent pairs where both functions are alive and both score
identically on every held-out sequence: **4B 2/14, 8B 6/28, 14B 0/22, 30B 0/26.
Eight of 90, all of them on the two small rungs.** Every one has a distinct
source SHA, so none is a resubmission. Two of the three clear 8B cases moved
their weights *non-uniformly*, by factors of four and five, and still changed
nothing, because `lines_cleared` decides whenever it is non-zero and the
remaining terms kept their ratios to each other. **The models are tuning the
numbers that never decide anything** — a sharper account of a flat curve than
"it is all noise", and one that only exists because the functions are on disk to
re-read.

### Two corrections the run forced

**Revisions do break the import rule.** All five of the run's rejections were
`import math` and four were revisions, against a published finding that read
"revisions never do it — 0 of 55". That zero was a *no occasion*: all five
occasions known the day before happened to fall at iteration 0. On the proper
denominator the conditions are 4 of 7 against 4 of 12, Fisher p = 0.377. One
chain imported at iterations 0, 2 and 4, was told each time in the validator's
own words, and complied at 1 and 5 — the error message works while it is in the
context window and not one step further.

**The 30B's one success loses its explanation.** Yesterday's pilot credited its
best chain to moving the weights "the direction the classic Tetris weightings
go". The 8B's chain 3 moved the same direction — hole penalty up 100×, line
reward halved — and fell from the run's best opening function to its worst
ending one, 34.57 to 11.46. Same direction, opposite outcome, so direction is
not the distinguishing thing and nothing currently is.

### And one hypothesis, flagged as one

The four revisions written immediately after a rejection — their prompts
carrying the validator's message and no game data at all — gained a mean
**+8.18**, against **+0.34** for the 41 revisions handed a full game report.
Permutation p = 0.032, and p = 0.027 against a span-matched control, so the
obvious confound is not it. But it was found after the fact, n is 4, two of the
four are one chain, and taking one observation per chain leaves p = 0.098. It is
written down as a hypothesis with its own 12-chains-a-group experiment attached,
because if it survived it would be the most uncomfortable result here: the loop
moving further when the feedback is removed.

Free by-product, from comparing two logs: **2 of 10 iteration-0 generations
reproduced byte-for-byte** against the ladder's 8B chains, under the same prompt
and per-chain seed at temperature 0.7 — while the *distribution* reproduced
closely (median 15.63 against 15.67, spread 13.09 against 13.36). A rung's noise
is a stable property even where its individual samples are not.

### The follow-up that disproved its own premise

`analysis/placement_diff.py` was written to replace the inertness count with a
better one: the published figure counted exact ties in the held-out totals,
which is a lower bound by construction, so a revision changing one decision in a
thousand would have counted as having changed something. Measured properly — the
game driven by the earlier function, both functions asked about every board it
reaches, 129 revisions and 304 seconds with no model calls — **the bound was
tight. The same 8 live pairs, no disagreement in either direction.** The
prediction that justified the analysis was wrong.

It earned its keep three other ways. There is a **near-inert class** the totals
cannot see: six revisions changed between one and three decisions, and the
sharpest moved **+1.04 points per piece on 3 decisions out of 1,949** — 41% of
the loop's whole median gain, produced by three choices. Unlike exact inertness,
which is confined to the 4B and 8B (8 of 8, with the 14B at 0 of 17 and the 30B
at 0 of 27), this class reaches the top two rungs. The **rate of change by rung**
came out 4B 7.4%, 8B 3.3%, 14B 3.7%, 30B 12.8%, so the one rung that starts with
working functions also rewrites them hardest — which sits awkwardly beside its
three regressions. And a two-seed trial of the same measure reported 10 of the
8B's 31 live revisions as inert where ten seeds give 6: **inertness is a claim
about every board, so too few boards can only over-report it.**

### And the term-level replay took the best result off the loop's ledger

The last cheap analysis, and the one that cost the most. Two revisions had moved
their weights the same direction to opposite ends, and both write-ups recorded
the same open question. `analysis/reweighting.py` holds each function's
structure fixed, changes only its numbers, and replays on the held-out seeds, so
each function is its own baseline and nothing depends on the rungs computing
their terms alike.

**The 30B's winning revision was not a reweighting.** Its iteration 0 computed
column heights by scanning *up* from row 19 and stopping at the first filled
cell, so on any board resting on the floor every height was `19 - 19 = 0`: the
height and bumpiness terms were dead. The capability probes had already said so
— `height: blind` — and the pilot's own §3 counted this chain among its three
repairs, while §4 of the same document credited it to reweighting. Crossing the
two factors: **repair alone +3.25, reweighting alone −3.90, both +9.16,
interaction +9.81.** The new weights make the broken function worse and are
worth +5.91 only once the terms they weight are alive. So the project's best
function came from the one thing the loop has been shown to do.

**And its predecessor's 41.55 was 63% an accident.** Remove the trailing
`unique_term` — a uniqueness hack worth at most 0.199 against terms scaled in
hundreds — and iteration 0 scores **15.29**. With dead height terms the function
ties at the maximum on **55% of decisions**, so the tie-breaker was the policy;
and because `row` is the piece's top row on a board whose row 0 is the top, it
preferred *lower* placements. Breaking ties at all is worth +7.17, preferring low
adds **+20.42**, and preferring high is worse than not breaking ties.

**The 8B's collapse was not the lines-and-holes move either.** Walking its
weights one at a time from iteration 0: `lines` 100→50 changed nothing, `holes`
1→100 **gained +6.44**, `max_h` 0.5→150 lost **18.34** and `unevenness` 0.1→150
lost **29.14**. Reverting unevenness alone recovers +15.14 of the 23.11. The
hole-penalty direction helped on both rungs; there was never a direction
producing two outcomes.

Three claims withdrawn in one afternoon, and all three move toward the project's
existing headline rather than away from it.

`docs/findings/the-best-powered-null-and-the-inert-revisions.md`,
`docs/findings/the-best-revision-was-a-repair.md`,
`runs/published/8b-loop/`, `runs/published/reweighting/`,
`src/tetris_bench/placement_diff.py`, `src/tetris_bench/reweighting.py`.

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
| Revisions avoid the `import math` error despite the revise prompt stating the rule worse | `revise_v1` was never used in any published run. The loop uses one template for every iteration, so the wording is identical at iteration 0 and at revision; the difference is the feedback block and the previous function, which is already import-free | `04cc3ca` |
| A properly aimed 30B loop needs 14–28 chains for a +8.04 gain | The paired σ_d was scaled from the 14B at 10.54; measured on the rung it is 16.76, too low by 1.59×, so the requirement is 34 chains. Three measured rungs give ratios of 0.70×, 1.05× and 2.39×, so the scaling method is retired, not re-tuned | 2026-11-24 |
| The best result needed no feedback at all | The best function is now iteration 5 of a six-step chain, at 50.19 points per piece against the previous best of 46.4. The loop produced it; with +8.64 inside a σ_d of 16.76 it cannot be credited with causing it | 2026-11-24 |
| Revisions never break the `import math` rule — 0 of 55 | A no-occasion, not a compliance: all five known occasions fell at iteration 0, so the condition had never been tested. The 8B loop added 12 revision occasions, 4 of which imported. Iteration 0 is 4 of 7, revisions 4 of 12, Fisher p = 0.377 | 2026-11-24 |
| The 30B's best chain worked because it moved its weights the direction the classic Tetris weightings go | The 8B's chain 3 moved the same direction — hole penalty up 100×, line reward halved — and lost 23.11 points per piece from the best opening function in its run. Direction is not what distinguished it, and nothing currently is | 2026-11-24 |
| A rung's paired σ_d relative to its cross-chain spread, published as 0.70×, 1.05× and 2.39× | Two different denominators: the 30B's used the standard deviation of the iteration-0 rates, the others `Curve.chain_spread()`. Recomputed with one definition the four rungs read 0.70×, 0.84×, 1.07×, 2.39×. The 3.4× span, and the retirement of the scaling method, hold either way | 2026-11-24 |
| Six revisions on the 4B "reweighted a crashing function", and similar steps elsewhere moved the score a little | Some revisions cannot move anything. 8 of 90 live adjacent revisions rewrote their weights and then chose identically on every held-out sequence; one is provably a no-op, every weight doubled | 2026-11-24 |
| The inert-revision count is a lower bound, because it only catches exact ties in the totals | Measured at the decision level it is exact: the same 8 live pairs, no disagreement either way. The prediction behind the follow-up analysis was wrong, though it did turn up 6 near-inert revisions the totals miss, one worth +1.04 points per piece on 3 decisions out of 1,949 | 2026-11-24 |
| The 30B's chain 1 is the project's only clean example of a revision getting a weighting right | It was a capability repair. Iteration 0's height and bumpiness terms were dead (`height: blind`, as its own probe data recorded), and the new weights are worth −3.90 on the unrepaired function against +5.91 on the repaired one, interaction +9.81 | 2026-11-24 |
| The 30B rung's iteration 0 reaches 41.55 points per piece, close to the hand-written heuristic, with no feedback | 63% of that was a trailing `unique_term` worth at most 0.199. Without it the function scores 15.29, because 55% of its decisions were ties at the maximum and the term preferred lower placements, which was the only strategy a height-blind function had | 2026-11-24 |
| The 8B's chain 3 collapsed because it moved the same direction as the 30B's winning chain, too far | Its lines-and-holes move gained +6.44 on its own. The collapse came from setting `max_h` and `unevenness` to 150 each, worth −18.34 and −29.14 alone | 2026-11-24 |

---

## Where it stands

**Every milestone is built and tested, under 779 unit tests.** Milestone 7, the
direct agent, landed as a single demonstration game rather than a full arm,
because 672 s per piece makes a powered version weeks of wall clock for a
baseline whose purpose is to be beaten; the cost ratio was its deliverable and
it is measured.

What remains is power, not coverage. **All four rungs have now been through the
loop** — the 14B, whose median rose +8.04 inside a bar of 10.95; the 4B, whose
median fell 4.63 inside a bar of 10.88; the 30B, +7.37 inside 19.16; and the 8B,
+2.51 inside 11.02. None shows a detectable change, on four rungs under one
byte-identical prompt, and every σ_d in that list is measured on its own rung's
chains rather than scaled from another's.

The 8B is the run that settled the shape of the answer. Ten chains made it the
best-powered curve here, and the bound it supports — **an 8B gain of eleven
points per piece or more is ruled out; a gain of five is not addressed** — is
the honest form of the headline. It is also the only rung where closing that gap
is affordable: 49 chains, about six hours, against 34 chains and twenty hours
for the same question on the 30B.

The afternoon's two cheap analyses then took the best result off the loop's
ledger. The 30B chain that reached 50.19 points per piece turned out to be a
**capability repair** rather than a reweighting — its iteration 0's height terms
were dead, and its new weights are worth −3.90 without the repair — and that
iteration 0's own 41.55 was **63% a tie-breaker** that accidentally preferred low
placements. Both findings move toward the project's existing headline rather
than away from it.

Two things the 8B found that no curve could have. **Eight of 94 live revisions
across the corpus rewrote their weights and then never once chose differently**,
on any board of ten full games — one provably, every weight doubled — with six
more changing at most one decision in two hundred. Both measures put every
exactly-inert case on the 4B or the 8B. And the four
revisions written with the feedback *removed* moved further than the 41 given a
full game report (p = 0.032, n=4, found after the fact), which is written down
as a hypothesis with an experiment attached rather than a result.

The outstanding list is in the README's [Not done](results.md#not-done); the
two cheapest items need no GPU at all, only the 227 functions already on disk.

> **Removed 2026-11-24.** A block stood here describing the `clean-6iter` run as
> "one clean six-iteration curve", the project's strongest and least trustworthy
> result, and ended by saying a per-chain model seed "is the next change, and
> nothing about the headline is quotable before it lands". All of that was true
> when written on 2026-11-20 and none of it has been true since 2026-11-21:
> `model_seed_for` landed, chains became independent, and four multi-chain
> curves have run on top of it. The reasoning it contained — that a bar
> excluding generation noise is no bar, that a gain measured up from a collapsed
> baseline is a different claim, and that large steps make a random walk look
> like a trend — is what the noise-bar and chain machinery was built from, and
> it is recorded in
> [the-improvement-curve-is-smaller-than-its-own-noise](results.md#the-improvement-curve-is-smaller-than-its-own-noise)
> and in the [Corrections](#corrections) table above.

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
6. ~~**The loop on a second rung.** Added here because it is now the top of the
   list: every statement this project makes about what the loop *does* rests on
   the 14B alone. The 8B at 10 chains, ~9.3 hours, is the run that turns one
   rung's behaviour into a measurement.~~ **Answered, and then some.** The loop
   has run on all four rungs — the 4B, the 14B, the 30B and finally the 8B at
   10 chains in 7 h 09 m — and none shows a detectable change. No statement
   about the loop now rests on one rung.
7. **An adequately powered curve, which only the 8B can afford.** 49 chains
   (~6 h) resolves a +5 there; the same resolution costs 34 chains and ~20 h on
   the 30B. Every null so far bounds the effect rather than excluding it, and
   this is the only way to tighten the bound.
8. **Does removing the feedback make a revision move further?** The 8B's four
   post-rejection revisions gained a mean +8.18 against +0.34 for the 41 given a
   full game report — p = 0.032, but found after the fact, with n=4 and p = 0.098
   once clustered by chain. Twelve chains a group with the rejection scripted,
   about 8.5 hours, would settle it. See
   [the-best-powered-null-and-the-inert-revisions.md](findings/the-best-powered-null-and-the-inert-revisions.md).
9. ~~**How many revisions change no decision at all?** Eight of 90 scored
   identically on every held-out sequence, which is a lower bound by
   construction — the test catches only exact ties. Replaying each adjacent pair
   over the same boards and counting *placements chosen differently* needs no
   model and no GPU.~~ **Answered, and the bound was tight.** Measured at the
   decision level over 94 live revisions: **the same 8 pairs, no disagreement in
   either direction**, so the published count stands. Six further revisions
   changed between one and three decisions — not ties, because a few choices
   move a total — and the sharpest moved +1.04 points per piece on **3 decisions
   out of 1,949**, which is 41% of the whole 8B loop's median gain.
   `analysis/placement_diff.py`, 304 s, no model calls.
10. ~~**What separates a good reweighting from a fatal one?** The 30B's chain 1
    and the 8B's chain 3 moved their weights the same direction to opposite ends,
    so the direction is not the answer and nothing currently is.~~ **Answered by
    dissolving it.** Neither revision was a reweighting in the way it read: the
    30B's was a **capability repair** whose new weights are worth −3.90 without
    it, and the 8B's lines-and-holes move **gained +6.44** while its two surface
    weights lost 18.34 and 29.14. The hole-penalty direction helped on both
    rungs. `analysis/reweighting.py`,
    [the-best-revision-was-a-repair.md](findings/the-best-revision-was-a-repair.md).
11. **Is there one ridge both models were walking along?** The sharper successor:
    a grid over the hole penalty and the two surface weights on a repaired
    structure. Same corpus, no GPU.
