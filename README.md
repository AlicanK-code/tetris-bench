# tetris-bench

A benchmark that measures how well LLMs **improve at Tetris across repeated attempts**,
not just how well they play once.

Each model plays the same seeded piece sequences, receives feedback on how it did, revises
its strategy, and plays again. The headline result is each model's **improvement curve**:
who learns fastest, who plateaus, and who regresses after a revision.

A secondary angle compares local models of increasing size -- a capability ladder
from roughly 4B to 30B, all on one MacBook. It was built to ask whether the
improvement loop lets a small model close on a larger one; the measurement found
no gap to close between 4B and 14B and a step at the top, so the question is
[restated rather than answered](#the-ladder-is-a-step-not-a-slope).

**Everything runs locally; no paid APIs.** The client supports cloud providers and
that path is tested, but no planned run uses one. Dollar cost is therefore always
zero, so the headline cost measures are tokens and wall-clock seconds.

## What we found

The project asks one question: **do these models get better at Tetris when they
are told how they did and allowed to try again?** The short answer, on the
evidence so far, is *no -- and the interesting part is what happens instead.*

Every claim here links to the evidence below, and the artifacts behind all of
them are in [`runs/published/`](runs/published/).

### 1. No model has been shown to improve

On the only rung the loop has been run on properly -- `qwen3-14b`, five
independent chains, six iterations, 300 held-out games -- the median rises from
12.5 to 20.6 points per piece. That looks like learning until it is measured
against the noise:

| | |
|---|---|
| gain, first to last | **+8** |
| bar a real change must clear | **13** |
| plateau (peak, measured) | **iteration 0** |
| chains gaining more than the noise | **0 of 5** |

The bar is generation noise: five chains given the *identical* iteration-0
prompt scored 12.5, 0.5, 35.4, 15.4 and 0.0. Two samples of the same request
differ by more than six revisions do. `analysis/curves.py` prints the verdict
itself -- *"gain +8, only 0.6x the noise bar of 13 - treat as indistinguishable
from noise"* -- and puts the peak at the attempt before any feedback existed.

So the headline the project set out to produce, an improvement curve with a
slope, is not there. [The detail](#the-improvement-curve-is-smaller-than-its-own-noise).

### 2. What the loop does instead is repair

Of 60 first attempts across four models, **37 were not bad strategies but broken
ones** -- code that cannot express a strategy at all, because it counts the empty
space above the stack as holes, or computes a height term that is identically
zero on every board. A score cannot tell those apart from a weak strategy; both
are just a low number. [How that is measured](#most-model-written-scorers-are-broken-not-bad).

That reframes what "improvement" has meant whenever it happened. The two chains
that moved by more than the noise moved in **opposite directions**:

- one rose from **0.0 to 10.0** points per piece by *deleting* two inverted terms — repair, not refinement
- one fell from **35.4 to 24.8** by *adding* a term blind to everything above the first gap

So the loop can fix code that was broken, and it can break code that worked. What
has not been observed is a working scorer being made meaningfully better.

### 3. The best result needed no feedback at all

The strongest function the benchmark has produced came from a **first attempt
with no feedback in its prompt**: 22 lines of lines, holes and bumpiness, with no
height term, from `qwen3-30b-a3b`. On unseen sequences it scores **46.4 points
per piece against a tuned hand-written heuristic's 43.5** -- parity with a
published 2013 evaluator, cold.

That is the project's best result and its most awkward one, because the loop had
nothing to do with it. [The comparison](#the-top-rung-matches-a-hand-written-heuristic-cold).

### 4. Given only outcome feedback, the models do not find their own bugs

Traced by replaying the saved functions rather than inferred from scores, one
chain measured column height as a row index on a board whose row 0 is the top --
rewarding tall stacks. The next revision **flipped the signs and scored well
without fixing the definition**. The revision after that corrected the definition
and silently zeroed three of five terms, and the score collapsed.

The model fixed its bug by accident and then broke it by correcting the accident.
Locating that defect from outcome feedback is the exact ability the benchmark
exists to measure. [The three functions](#the-strongest-result-is-a-credit-assignment-failure).

### 5. Scale gives a step, not a slope

The secondary question -- does the loop let a small model close on a large one --
turned out to be ill-posed, because there is no gradient to close. `qwen3` at 4B,
8B and 14B are statistically indistinguishable in how often they write a working
scorer (every pairwise Fisher p >= 0.68), and the 30B-a3b jumps clear of all three
(p = 0.002). The rung that separates is also the only mixture-of-experts model, so
size and architecture are confounded and the honest claim is narrower than
"capability scales with size". [The ladder](#the-ladder-is-a-step-not-a-slope).

### What would change these answers

The negative result is **narrow, not final**, and the main limit is coverage:

- **The loop has only ever run on one of the four rungs.** The other three have
  measured iteration-0 baselines and no revisions. A model that improves where
  the 14B does not would change answer 1 outright. How much sampling that takes
  is now quantified per rung by
  [the power analysis](docs/findings/30b-loop-is-underpowered-not-futile.md):
  on the 30B it needs 14 to 28 chains rather than the five used so far, and the
  8B is the better first spend.
- **Six iterations may be too few**, and five chains is a small sample against a
  noise floor this wide.
- **The feedback is deliberately symptoms-only** -- score, lines, holes, height,
  cause of death, board snapshots. Richer feedback would very likely move the
  curve; it would also stop measuring self-diagnosis, which is the point.

What the project does have is the machinery to answer the question properly:
held-out evaluation, independent chains, a measured noise floor, capability
probes that separate broken code from bad strategy, and a headline that a piece
budget cannot distort. Several of the findings above only became visible because
one of those was in place, and several earlier conclusions have been **withdrawn
or corrected in place** when a better measurement contradicted them -- each one
marked where it was claimed rather than quietly edited, because the sequence of
wrong turns is part of what the project is demonstrating.
[How these documents are written](docs/findings/).

## Status

The engine, baseline agents, rendering and run records, the model client, the
sandboxed strategy agent, the improvement loop and the analysis all work, under
698 unit tests. Every milestone that was going to be built is built; what
remains is measurement, and the measurement has reframed the headline -- see
[Results](#results).

| # | Milestone | State |
|---|-----------|-------|
| 1 | Engine (pieces, rotation, collision, line clears, 7-bag, legal placements) | **done** |
| 2 | Baselines (random + hand-written heuristic agent) | **done** |
| 3 | Rendering + metrics | **done** |
| 4 | Model client (OpenAI-compatible, local + cloud) | **done** |
| 5 | Strategy agent + sandbox | **done** |
| 6 | Improvement loop | **done** |
| 7 | Direct agent | **done**, one demonstration game, see [Results](#direct-mode-costs-800x-and-plays-like-random) |
| 8 | Analysis (curves, ladder gap, tokens/seconds per point) | **done**, ladder measured on all four rungs |

## Setup

Requires [uv](https://docs.astral.sh/uv/); uv supplies Python itself, pinned to
3.13 in `.python-version`.

```bash
uv sync --all-extras
uv run pytest
uv run ruff check . && uv run ruff format .
```

**Use `--all-extras`, not one extra at a time.** `uv sync` resolves the
environment to exactly what is asked for, so `uv sync --extra analysis`
*uninstalls* the `llm` extra and leaves the model client missing. Both are
needed on the same machine, because a run is played and then plotted.

## Engine design notes

Three narrowings make the engine small and the benchmark sharper. All are
additive to undo later.

- **Hard-drop placements only.** A move is "rotate in free space, pick a column,
  drop straight down". No tucks or slides under an overhang. This keeps
  `legal_placements` a pure function of the board and short enough to show a
  model in a prompt, and keeps the measurement on *position scoring* rather than
  on spotting clever slides.
- **No SRS wall kicks, and deduplicated rotations.** Because a piece is never
  rotated against an obstruction, only the set of *distinct* shapes matters. So
  `O` has 1 rotation state, `I`/`S`/`Z` have 2, and `T`/`J`/`L` have 4. A
  rotation index is an index into that tuple and deliberately does not always
  match SRS numbering. The payoff is that a model is never offered the same move
  twice as if it were a real choice.
- **A piece budget, not a time limit.** A game ends on `block_out` (the next
  piece has nowhere to land) or `piece_limit`, default 2000. A competent
  heuristic stacks cleanly for a very long time -- the reference one averages
  10,467 pieces and varies by more than its own mean -- so without a cap a run
  takes an unpredictable length of time; capping pieces rather than wall-clock
  time also keeps every model's game the same length. The budget makes `score` a
  **censored** measure, which matters more than it sounds -- see
  [Reference baselines](#reference-baselines).

Line scores are the classic 100 / 300 / 500 / 800 for 1-4 rows, with no level
multiplier since there is no gravity to speed up.

## Reference baselines

Two reference players, on the 20 held-out seeds the improvement curve is read
from, at the default 2000-piece budget.

| agent | what it does | mean score | mean pieces | points/piece | lines/piece | censored |
|-------|--------------|-----------:|------------:|-------------:|------------:|---------:|
| random | uniform over legal placements | 10 | 26 | 0.4 | 0.00 | 0/20 |
| heuristic | Lee's 2013 weights, 1-ply | 76,040 | 1,762 | **43.2** | **0.40** | 14/20 |

**The heuristic's total score is nearly unmeasurable, and that changes how
everything else gets quoted.** Run it to exhaustion -- a 50,000-piece budget,
where it dies on its own on all 20 seeds -- and it averages 454,900 points over
10,467 pieces with a standard deviation of **470,079**. A coefficient of
variation above 100% means a single game says almost nothing, and pinning the
mean to even 10% would take hundreds of games.

Its *rate*, meanwhile, is 43.5 points per piece, and holds at 43.2-43.5 across
every budget tried: 500, 2,000, 20,000, 50,000. One of these two numbers is a
usable comparator and the other is not.

At the 2000-piece budget runs actually use, the heuristic is censored on 14 of
20 seeds, so its total there is a lower bound and "beat 21,600" was really "beat
the 500-piece budget". A censored agent also looks *more* consistent than it is,
because the cap truncates exactly the games that would have run long -- which is
why the +/- 21,065 at the 2000-piece budget understates the +/- 470,079 that is
really there.

So the benchmark reports two separable things and declines to collapse them:

- **survival** -- does the agent die, and after how many pieces?
- **rate** -- points and lines per piece *while alive*, the only figure that
  survives a change of budget.

That separation is what makes the headline in [Results](#results) legible: the
best model-written function reached 92% of the heuristic's *rate* while dying
after 626 pieces. Those are two different failures, and the ratio of two
truncated totals hid both.

```bash
uv run python analysis/baseline_ceiling.py
uv run python analysis/baseline_ceiling.py --max-pieces 20000 --seeds 5
uv run tetris-bench play --agent heuristic --seed 1
```

The random agent never clears a line on most seeds, which makes it a floor
rather than a competitor. Earlier revisions of this table carried a third
"naive" row -- drop each piece as deep as it will go, ~1,675 points. It is gone
because no such agent exists in the codebase, so the row could not be reproduced
from this repo; a few `analysis/` scripts still print the figure as a hardcoded
reference literal.

## Agent design notes

**The scoring function is the primitive, not the agent.**
`ScoringFunction = Callable[[Board, Placement], float]` rates one candidate move,
and `ScoringAgent` is a small adapter that applies a scorer to every legal
placement and keeps the best. The heuristic agent is `ScoringAgent` plus a
weighted sum of board features.

This matters for milestone 5. `strategy` mode asks a model to write exactly a
`score(board, placement) -> float` function, so a model-written scorer is the
same *kind* of object as the hand-written heuristic and the comparison is
apples-to-apples. `Agent` stays the general interface, since "choose uniformly at
random" is not a per-placement rating.

**`StrategyAgent` is a separate class, not a `ScoringAgent`.** Both follow "rate
every legal placement, keep the best", but they cannot share the adapter, because
the sandbox boundary changes the contract: the heuristic receives the pre-move
`Board` and calls `apply_placement` itself, whereas a sandboxed function is
handed the *post-move* board already flattened to tuples of bool plus a dict
carrying `lines_cleared`. Crossing a process boundary one placement at a time
would also be unaffordable, so `StrategyAgent` batches a whole piece's candidates
into one call. The duplication is real and deliberate; calling it "the same
adapter" would be wrong.

**Features are measured after the move, not before.** The heuristic scores the
board a placement *would produce*, once the piece is locked and any completed
rows are cleared. Scoring the current board would rate every candidate
identically, because the board is the same for all of them.

**Two independent seeds per run.** One for the piece sequence, one for the
agent's own randomness. The random agent owns its own `random.Random` instance:
sharing the game's piece RNG would let the agent's draws shift the piece
sequence, so two agents would face different games and the premise that every
model plays identical seeds would fail silently.

**Weights are a frozen dataclass**, defaulting to the values published by Yiyuan
Lee in ["Tetris AI - The (Near) Perfect
Bot"](https://codemyroad.wordpress.com/2013/04/14/tetris-ai-the-near-perfect-player/)
(2013), found with a genetic algorithm. They are used unmodified so the baseline
does not move. Note Lee tuned them for a 10x22 board with one lookahead piece, so
they are optimised for a near neighbour of this engine's rules rather than for it
exactly -- a reference ceiling, not a published optimum here.

## Prompt rendering

Everything a model reads is built in `render.py`, so the whole model-facing
surface sits in one reviewable file.

The board is 20 rows; the empty rows above the stack are trimmed here.

```
0123456789
..........
..........
##.......#
##......##
##.....###
#.#####.##

current piece   I
next pieces     Z S O L Z
score           2300
lines cleared   22
pieces placed   60
max height      4
holes           2
bumpiness       6
```

```bash
uv run tetris-bench play --seed 1 --max-pieces 60 --show-state
```

**A column index row sits above the grid.** A placement is named by rotation and
column, so a model can read the column number straight down rather than counting
cells, which is exactly the sort of thing it will get wrong.

**Filled cells are `#`, not the piece letter.** Tetris is Markovian in occupancy:
which placements are legal, which rows clear and what the board becomes next
depend only on whether a cell is filled, so the identity of the piece that filled
it cannot change the best move. The letters are not meaningless -- they show how
a stack was built -- but they are decision-irrelevant, and they cost tokens and
ask the model to treat seven symbols as equivalent. `--show-pieces` brings them
back for inspecting a game by hand; note that feedback snapshots do **not** use
it and always render `#`.

**A numbered list of legal moves exists but nothing currently consumes it.**
`render_placements` produces:

```
 0  rot=0 col=0 lands row 15
 1  rot=0 col=1 lands row 15
 2  rot=0 col=2 lands row 18
```

The intent was that choosing from a handed list cannot produce an illegal move,
whereas describing one freely can. That rationale belongs to `direct` mode, which
was [cut to a demonstration](#not-done) -- so in the only live mode the model
writes a scoring function and never answers with an index. The renderer and its
tests are kept because the direct-agent demonstration still needs them.

**There is no hold piece.** Hold roughly doubles the branching factor per turn
for a benchmark about scoring-function quality, not move vocabulary.

## Run records

Two layers rather than one flat dataclass. `GameResult` is what a finished game
produced and knows nothing about models, so the baseline agents emit a complete
record with nothing left empty. `RunRecord` wraps one with the model-side facts
-- model, mode, iteration, and tokens, latency and cost. They flatten to a
single-level JSON object at write time, so the JSONL on disk loads straight into
a dataframe:

```json
{"agent": "heuristic", "agent_seed": null, "avg_bumpiness": 6.45, "avg_holes": 0.8,
 "avg_max_height": 3.65, "cause": "piece_limit", "final_aggregate_height": 22,
 "final_bumpiness": 6, "final_holes": 2, "final_max_height": 4, "lines_cleared": 22,
 "pieces_placed": 60, "score": 2300, "seed": 1}
```

```bash
uv run tetris-bench play --agent heuristic --seed 1 --log runs/baseline.jsonl
```

Averages are sampled after every placement rather than read off the final board,
because a game that ends tall may have been played low for most of its length,
and the reverse. JSONL rather than one JSON array because a run that crashes
leaves every completed game already on disk and readable.

## Model client

One OpenAI-compatible client serves local runtimes and cloud providers alike, so
the provider is configuration rather than code and swapping a 30B local model for
a frontier one is a config edit.

```bash
uv sync --all-extras
uv run tetris-bench models
```

```
name       provider  model          in $/M  out $/M  key
qwen3-4b   ollama    qwen3:4b       0       0        not needed
qwen3-8b   ollama    qwen3:8b       0       0        not needed
qwen3-14b  ollama    qwen3:14b      0       0        not needed
qwen3-30b  ollama    qwen3:30b-a3b  0       0        not needed
```

That command validates configuration without touching the network, and reports
whether each model's key is present -- the one setup mistake worth catching
before a run rather than during one. Everything live in the committed config is
local and free; a paid entry is kept commented out to document the shape.

**Known providers live in code, configs name one.** Ollama and LM Studio serve on
fixed localhost ports and need no credential, so a config entry says which
provider and which model and nothing that would be identical in every file.
`base_url` and `api_key_env` can still be overridden for a remote box or a
gateway.

**Pricing lives in the config.** Each entry declares dollars per million tokens;
local models declare zero. Since a run must be reproducible from its config and
seed list, and prices change, a cost logged months ago stays explainable by the
file that produced it.

**The code's temperature default is 0, and a seed is set -- but neither makes
generation reproducible.** Measured: two runs of a byte-identical prompt at
temperature 0 with a fixed seed produced different functions on the 4B and on the
30B, where the two scored 0 and 1,700. The seed is honoured, so sampling is not
the cause; floating-point non-associativity is, and no seed removes it.
Reproducibility is a property of the (model, prompt) pair and is measured per
rung -- see [docs/findings/](docs/findings/). The engine itself is provably
deterministic; this is entirely model-side.

**Every configured rung overrides that default to `temperature: 0.7`, because
`--chains` does not work at 0.** Greedy decoding takes the argmax at every step
and never draws from the RNG, so a per-chain seed has no random number to index:
measured, three seeds at temperature 0 return one byte-identical generation, and
at 1.0 return three different ones. A multi-chain sweep at temperature 0
therefore draws **one** sample and pays N times for it -- which a five-chain run
discovered the expensive way, with four of its five chains byte-identical.

`temperature`, `frequency_penalty`, `max_tokens` and `max_retries` are
**identical on all four rungs** by design. Each was first added to the 14B alone
to fix a specific problem, and leaving them there would have confounded model
size with sampling configuration -- a 4B truncated at a different token budget
than the 14B looks worse for a reason that has nothing to do with being a 4B.
One consequence worth stating: the live configs set `max_retries: 0`, so the
retry machinery described below is exercised by the test suite rather than by any
run in `runs/`.

**Transient failures are retried in the client**, with exponential backoff capped
at 30s, so callers only handle *semantic* failures: output that will not parse, a
scoring function that will not compile. A dropped connection, a timeout, a rate
limit and a 5xx are retried; a bad key, a malformed request and a missing model
are not, because retrying those just burns time and quota.

**Retries are tallied apart from calls.** `model_calls` counts logical calls so
cost-per-call stays meaningful, `retries` records provider flakiness separately,
and `failed_calls` counts calls that never succeeded. Latency is wall-clock and so
includes time spent retrying, because that is what a run costs in time. A failed
call still updates the tally: a run's cost includes the calls that did not work.

**The transport is injected**, so every test runs with no network, no API key and
no local model. That matters because the code recording failures has to be
exercised on purpose rather than when a provider happens to be down.

**Cost is measured in tokens and seconds, not dollars.** Local inference is free,
so `estimated_cost_usd` reads zero on every run. It stays in the schema so a paid
model could be added without a migration, but tokens-per-point and
seconds-per-point are the figures that mean anything here -- tokens being the
hardware-independent one, and seconds being what you actually wait for.

Cloud providers go through their OpenAI-compatible endpoints, so adding one is a
config entry rather than new code. The benefit of the single path is that local
and hosted runs are directly comparable; the cost is that provider-specific
features are unavailable through a compatibility layer.

## Results

Every figure below is read from **held-out** seeds whose outcomes the model never
saw, at zero dollars.

**The headline measure is points per piece, not total score.** A total is
censored by the piece budget -- a game that hits the cap is cut off rather than
finished, so its score is a lower bound, and the best function here was censored
in 8 of 10 games. A rate does not have that failure mode and is empirically
budget-independent: the hand-written heuristic measures 43.2-43.5 points per
piece at 500, 2,000, 20,000 and 50,000 pieces alike. Totals are still reported
beside it, because survival is a separate thing worth knowing. Rates are totals
over totals across a position's ten unseen sequences, which is what the
baseline's own 43.5 is (454,900 / 10,467).

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
| *hand-written heuristic* | — | *43.5* | *43.5* | *84,720* | *84,720* |

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
quotable](docs/findings/size-ladder-is-a-step.md).

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
| *heuristic (Lee 2013)* | *43.5* | *84,720* | *10,467* | — |

**Chain 3 wins on totals by surviving longer; chain 4 actually scores faster.**
That inversion is the switch to a rate earning its keep. Chain 3's 81,300 was a
lower bound -- censored in 8 of 10 games -- so the old headline was partly
reporting the budget. Chain 4 is censored once in ten, which makes its 46.4 the
more trustworthy figure of the two.

So the result is that a 4-bit local model, on its first attempt, **matches the
scoring rate of a tuned hand-written heuristic** -- 46.4 and 43.4 against 43.5.
Read that as parity rather than a win: the heuristic's rate is measured over
10,467 pieces and chain 4's over about 1,034, and a rate measured over a shorter
run has had less chance to meet the board states that punish a weak evaluator.

Chain 4's function is 22 lines of lines, holes and bumpiness with **no height
term at all**. One chain in fifteen reproduced a Dellacherie-style evaluator
cold.

It stays an awkward result for this project, and worth saying plainly: the best
function the benchmark has produced **arrived without the improvement loop**.

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
[`runs/published/clean-6iter/`](runs/published/clean-6iter/) -- a different run
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
| heuristic (Lee 2013) | 43.5 | 10,467 |
| 14B, iteration 4 | 40.2 | 626 |

**About 92% of the heuristic's scoring rate, and 6% of its survival.** The model
learned to clear lines about as efficiently as a tuned hand-written heuristic
and never learned to stay alive. Quoting totals alone would have called this
"69% of the heuristic" and hidden both halves -- see
[Reference baselines](#reference-baselines).

This was the observation that eventually moved the headline onto a rate. It is
no longer the best rate in the project -- the 30B's 46.4 is -- but it is still
the clearest demonstration of *why* the two have to be reported separately.

```bash
uv run python analysis/baseline_ceiling.py --max-pieces 50000 --seeds 20
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
[docs/findings/direct-mode-costs-800x-and-plays-like-random.md](docs/findings/direct-mode-costs-800x-and-plays-like-random.md).

```bash
uv run tetris-bench play --agent heuristic --seed 1 --max-pieces 20   # instant
uv run tetris-bench direct --model qwen3-14b --seed 1 --max-pieces 20 # 3h44m
```

### Findings with their own write-ups

Each of these is a separate experiment in [docs/findings/](docs/findings/), with
the generated functions as artifacts. They are written as the result was found
and corrected in place with a dated note when something later overturned them --
five of them currently carry one.

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
  slope](docs/findings/size-ladder-is-a-step.md)** -- all four rungs at
  iteration 0, 15 chains each, one byte-identical prompt. Also records the
  project's first four rejections, three of which were `import math` against a
  prompt that forbids imports in bold, making them instruction-following
  failures rather than harness artefacts.
- **A bad strategy and one that cannot be expressed look identical in a score**,
  which is why the capability probes exist. Both produce a low number, and 37 of
  60 first attempts were in the second category.
- **[Direct mode costs 800x and plays like
  random](docs/findings/direct-mode-costs-800x-and-plays-like-random.md)** --
  the milestone 7 demonstration. 3 h 44 m for 20 pieces, 86 holes against random
  play's 70.6, and 0 malformed replies, so the failure is choice and not
  formatting.

### Not done

Ordered by whether it would change anything claimed above.

**One experiment would.** Everything in [What we found](#what-we-found) rests on
the loop having been run on **one rung**: the 14B. The ladder measured all four
rungs at *iteration 0 only*. So "no model has been shown to improve" and "the
largest gain ever observed is +10.0" are statements about one model currently
being quoted as statements about the mechanism.

- **The loop on a second rung -- the 8B, 10 chains, 6 iterations, ~9.3 hours.**
  The 8B because it has the project's best **headroom-to-noise ratio, 2.29
  against the 30B's 1.31**: not the cheapest run, but the one with the most room
  for a result to appear in. See
  [the power analysis](docs/findings/30b-loop-is-underpowered-not-futile.md).
  This is the only outstanding item that could move a headline.

**One pilot would shore up a soft spot in the analysis.**

- **The 30B at 6 chains, ~3.5 hours.** Every power claim in this repo uses a
  paired standard deviation **scaled from the 14B** (8.74 x 15.13/12.55),
  because the paired figure has never been measured on the 30B at all. Six
  chains measure it directly. The finding that makes those claims says so
  itself.

**Four things cost nothing and are answerable from logs already on disk.**

- **The rate of zeros as its own effect.** Three of the 30B's 15 chains scored
  0.0. If the loop's value on that rung is *rescuing dead functions* rather than
  improving live ones, the effect is a change in a proportion -- a different
  power calculation from the one in the write-up, and one the current analysis
  cannot see.
- **Does the loop move the probe-clean fraction?** 37 of 60 first attempts were
  broken rather than bad. This is the restated form of the "does a small model
  close on a large one" question, and the ladder left it open.
- **The `import math` rejections.** Three of the project's four rejections were
  `import math` against a prompt that forbids imports in bold, which makes them
  instruction-following failures rather than harness artefacts. Worth
  quantifying rather than mentioning.
- **Whether `strategy_v2`'s "must discriminate" warning worked**, from
  [the 4B write-up](docs/findings/qwen3-4b-iter0-detailed.md)'s open questions.

**Two are held rather than planned.**

- **The counterexample arm, rerun on the fixed script (~4.2 h).** The
  per-board reading was withdrawn when the sweep turned out never to have varied
  its seed; the board question reopened at **Fisher p = 0.07 one-sided**, which
  is suggestive and not settled. See
  [the write-up](docs/findings/counterexample-is-the-sampler-not-the-board.md).
- **Is `qwen3-8b` reproducible?** 19-30 minutes, documentation value only. The
  14B is the only rung shown reproducible and only on the iteration-0 prompt;
  this is not a gate on the 8B loop.

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
[`runs/published/`](runs/published/) holds the generated functions plus the
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
[its own README](runs/published/README.md) indexes what each run supports.

## Licence

[MIT](LICENSE). The heuristic baseline weights are from Yiyuan Lee's 2013 post,
credited in [Agent design notes](#agent-design-notes).
