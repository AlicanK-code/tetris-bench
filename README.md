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

**All four rungs have now been run through the loop, and the best-powered of
them is the 8B:** ten independent chains, six iterations, 550 held-out games, a
measured paired σ_d of 12.44. Its median gain is **+2.51** against a minimum
detectable gain of **11.02**, seven chains up and three down, sign test
p = 0.344. That run can rule out an improvement of eleven points per piece and
says nothing about a gain of five -- which is the tightest bound here, and the
shape of every other rung's answer too.

On `qwen3-14b` -- five chains, six iterations, 300 held-out games -- the median
rises from 12.5 to 20.6 points per piece. That looks like learning until it is
measured against the noise:

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

On `qwen3-4b`, under the identical protocol, the median **falls** from 7.5 to
3.7 -- also inside its own noise, which is 10.9 there. Three of its five chains
ended below where they started. The 30B's +7.37 sits inside a σ_d of 16.76, the
widest of the four.

| rung | chains | median gain | σ_d | detectable at that n |
|---|---:|---:|---:|---:|
| `qwen3-4b` | 5 | −4.63 | 8.69 | 10.88 |
| **`qwen3-8b`** | **10** | **+2.51** | **12.44** | **11.02** |
| `qwen3-14b` | 5 | +8.04 | 8.74 | 10.95 |
| `qwen3-30b` | 6 | +7.37 | 16.76 | 19.16 |

Every σ_d there is measured on that rung's own chains. None is scaled from
another's, because [the scaling inverts](#the-improvement-curve-is-smaller-than-its-own-noise):
the ratio of a rung's paired σ_d to its between-chain spread runs 0.70, 0.84,
1.07 and 2.39 across the four.

Three ways the loop could have been improving something the curve cannot see
have each been checked and each come back null: the mean, the fraction of
functions that can express a strategy at all, and the fraction that score
nothing. A fourth check, added with the 8B, found the opposite of hidden
progress -- **8 of 94 live revisions across the corpus rewrote their weights and
then never once chose differently**, on any board of ten full games, one of them
provably unable to. Six more changed at most one decision in two hundred. So the headline the project set out to produce, an
improvement curve with a slope, is not there on any of the four rungs.
[The 14B detail](#the-improvement-curve-is-smaller-than-its-own-noise),
[the 4B's](#the-loop-shows-nothing-on-a-second-rung).

### 2. When the loop moves anything, it is repair and damage, not refinement

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

**And measured across all four completed loops, it does the second slightly
more often than the first: 10 repairs in 83 chances against 9 regressions in
50.** A broken function is repaired 12% of the time it could be, and a working
one breaks 18% of the time it could, over 133 transitions; the sign test on the
19 discordant pairs gives p = 1.000. The 8B supplies more repair opportunities
than the other three rungs together -- 33 of the 83 -- and still does not beat
its own breakage rate. Revision moves
individual terms about -- 6 repaired and 7 broken on the 4B -- but capability is
a conjunction over terms, so fixing them one at a time while breaking others is
a walk that does not arrive.
[The measurement](#the-loop-does-not-repair-capability-either).

### 3. The best result came out of the loop, and still cannot be credited to it

> **Corrected 2026-11-24.** This finding previously read "the best result needed
> no feedback at all", on the strength of a 46.4 first attempt. The 30B pilot
> overturned that: its best function came after five revisions. The claim as
> stated is withdrawn, and what replaces it is weaker in a different way.

The strongest function the benchmark has produced is **iteration 5 of a six-step
chain**, at **50.19 points per piece** over about 18,000 held-out pieces --
above the tuned hand-written heuristic's 43.5. It is also the project's only
clean example of a revision getting a weighting right: across five steps the
hole penalty rose from 20 to 350 while the line reward fell from 100 to 10.

> **Amended 2026-11-24.** That last clause used to end "...which is the
> direction the classic Tetris weightings go", offering the direction as the
> explanation. The 8B loop supplies a counterexample: its chain 3 made the same
> qualitative move -- hole penalty up 100×, line reward halved -- and **lost
> 23.11 points per piece**, the worst collapse in that run, from the best
> opening function in it. Same direction, opposite outcome, so the direction is
> not what distinguished the 30B's success. What does is now an open question.

**That is not evidence the loop works.** Its +8.64 gain sits well inside this
rung's own noise -- a paired σ_d of 16.76, a minimum detectable gain of 19.16 at
six chains -- and in the same run two chains fell by 13.4 and 25.9 points, one
of them declining at every single revision. The loop produced the best function
the project has; it has not been shown to be the reason.
[The run](#the-30b-ships-the-best-function-and-the-worst-collapse).

### 4. Given only outcome feedback, the models do not find their own bugs

Traced by replaying the saved functions rather than inferred from scores, one
chain measured column height as a row index on a board whose row 0 is the top --
rewarding tall stacks. The next revision **flipped the signs and scored well
without fixing the definition**. The revision after that corrected the definition
and silently zeroed three of five terms, and the score collapsed.

The model fixed its bug by accident and then broke it by correcting the accident.
Locating that defect from outcome feedback is the exact ability the benchmark
exists to measure. [The three functions](#the-strongest-result-is-a-credit-assignment-failure).

**And it is not only outcome feedback.** The 4B loop produced a chain whose
function crashed on every call, where the feedback contained the interpreter's
own `UnboundLocalError` naming the offending variable. It carried that line
through **five consecutive revisions**, changing the weights around it each time.
[The five functions](#the-loop-shows-nothing-on-a-second-rung).

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

- **The loop has now run on all four rungs**, and none produced a detectable
  change. Coverage is no longer the limit; sampling is. How much sampling each
  rung takes is quantified by
  [the power analysis](docs/findings/30b-loop-is-underpowered-not-futile.md),
  with the caveat the 30B pilot added and the 8B confirmed: a paired σ_d must be
  **measured, not scaled**. The four measured rungs give ratios of 0.70x, 0.84x,
  1.07x and 2.39x against their cross-chain spreads, so there is no constant to
  borrow.
- **Resolving a small gain is affordable on exactly one rung.** On the 8B, 49
  chains would resolve a +5 (about 6 hours) and 193 would resolve the +2.51 it
  actually showed. On the 30B the same question costs 34 chains at roughly 20
  hours. If the project runs one adequately powered curve, the 8B is where.
- **Six iterations may be too few**, and on three of the four rungs five or six
  chains is a small sample against a noise floor this wide.
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
721 unit tests. Every milestone that was going to be built is built; what
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
| 8 | Analysis (curves, ladder gap, tokens/seconds per point) | **done**, ladder and the loop on all four rungs |

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
[docs/findings/the-discriminate-warning-does-not-fix-inert-arithmetic.md](docs/findings/the-discriminate-warning-does-not-fix-inert-arithmetic.md).

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
[docs/findings/the-import-rule-fails-three-times-in-five.md](docs/findings/the-import-rule-fails-three-times-in-five.md).

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
[docs/findings/the-zeros-rate-does-not-move-either.md](docs/findings/the-zeros-rate-does-not-move-either.md).

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
[docs/findings/the-loop-does-not-repair-capability.md](docs/findings/the-loop-does-not-repair-capability.md).

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

That is a sharper version of [finding 4](#4-given-only-outcome-feedback-the-models-do-not-find-their-own-bugs).
There the defence "it was never told what was wrong" is available. Here it was
told, in the interpreter's own words, five times.

**It also broke a power assumption of this project's own.** The 4B's paired
standard deviation is **2.39x** its cross-chain spread, where the 14B's is
**0.70x** -- the opposite direction. The 30B's published 14-chain requirement
scales from the 14B's ratio and is now a lower bound. Paired noise has to be
measured per rung.

Full write-up:
[docs/findings/4b-loop-reweights-a-crash-five-times.md](docs/findings/4b-loop-reweights-a-crash-five-times.md).

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

[The full write-up](docs/findings/the-30b-ships-the-best-function-and-the-worst-collapse.md)
· [the artifacts](runs/published/30b-pilot/)

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
**below the hand-written heuristic's 43.5**, and no 8B game was censored, so
unlike the 30B's figures these rates are uncensored throughout. And comparing
this log with the ladder's, **2 of 10 iteration-0 generations reproduced
byte-for-byte** under the same prompt and per-chain seed at temperature 0.7 --
while the *distribution* reproduced closely (median 15.63 against 15.67,
spread 13.09 against 13.36), so a rung's noise is stable even where its samples
are not.

[The full write-up](docs/findings/the-best-powered-null-and-the-inert-revisions.md)
· [the artifacts](runs/published/8b-loop/)

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
six of them currently carry one.

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
- **[The discriminate warning does not fix inert
  arithmetic](docs/findings/the-discriminate-warning-does-not-fix-inert-arithmetic.md)**
  -- 3 of 123 warned generations are still inert, all 4B, and the only
  controlled pair shows no effect. Also a measurement trap: a one-board probe
  over-reports flatness five-fold.
- **[The import rule fails two times in
  five](docs/findings/the-import-rule-fails-three-times-in-five.md)** -- the
  right denominator is the generations that wanted `math`, not the ones that did
  not. A bolded rule carrying its own worked example, ignored by **8 of the 19
  occasions** in a 227-generation corpus. Its own "revisions never do it" was a
  no-occasion, not a compliance, and is overturned.
- **[The zeros rate does not move
  either](docs/findings/the-zeros-rate-does-not-move-either.md)** -- 5 revivals
  against 5 deaths, p = 1.000, and the sample size that would have been needed:
  15 to 55 chains against the 5 that ran. Over four rungs and 130 transitions it
  is **14 revivals against 11 deaths, p = 0.690**.
- **[The loop does not repair capability
  either](docs/findings/the-loop-does-not-repair-capability.md)** -- 1 repair in
  40 chances against 2 regressions on the first two rungs, and **10 in 83
  against 9 in 50** over all four rungs. A broken function is repaired 12% of
  the time it could be; a working one breaks 18%. Closes the question the ladder
  left open.
- **[The 4B loop reweights a crashing function five
  times](docs/findings/4b-loop-reweights-a-crash-five-times.md)** -- the second
  rung past iteration 0. No detectable change, a chain that carried an
  `UnboundLocalError` through five revisions with the traceback quoted back to
  it, and a power assumption of this project's own broken.
- **[The 30B ships the best function in the project and its worst
  collapse](docs/findings/the-30b-ships-the-best-function-and-the-worst-collapse.md)**
  -- the power pilot. A measured paired σ_d of 16.76 against the 10.54 this repo
  had published, which turns a 14-28 chain requirement into 34; the first rung
  with working functions to refine, ending with as many as it started; and one
  chain that declined at all five revisions after inverting a sign that sits,
  harmlessly, inside the project's second-best function too.
- **[The best-powered null, and the revisions that change
  nothing](docs/findings/the-best-powered-null-and-the-inert-revisions.md)** --
  the fourth rung, and the largest run in the project: 10 chains, a measured
  σ_d of 12.44, median gain **+2.51** against a detectable 11.02. It also found
  revisions that **cannot** change anything -- 8 live revisions rewrote their
  weights and then never once chose differently on any board of ten full games,
  all 8 on the two small rungs, one of them provably so, with 6 more changing at
  most one decision in two hundred -- and a counterexample that costs the 30B
  pilot its explanation for its single success.
- **[Direct mode costs 800x and plays like
  random](docs/findings/direct-mode-costs-800x-and-plays-like-random.md)** --
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
  [the power analysis](docs/findings/30b-loop-is-underpowered-not-futile.md).
- **The post-rejection effect**, which the 8B run turned up and could not
  settle: revisions written with the feedback removed moved further than
  revisions given a full game report (p = 0.032, n=4, found after the fact).
  Twelve chains a group with the rejection *scripted* rather than waited for,
  about 8.5 hours. It is the one open question whose answer would be
  uncomfortable either way. See
  [the write-up](docs/findings/the-best-powered-null-and-the-inert-revisions.md).

**Two cheap analyses are left**, both answerable from the logs on disk with no
GPU at all.

- ~~**Count placements chosen differently**, rather than exact score ties.~~
  **Done** (`analysis/placement_diff.py`). The lower bound turned out tight --
  the same 8 pairs, no disagreement either way -- so the published count stands.
  It added a near-inert class of 6 more revisions, a per-rung rate of change, and
  the warning that too few seeds over-reports inertness.
- **What separates a good reweighting from a fatal one.** The 30B's chain 1 and
  the 8B's chain 3 moved their weights the same direction to opposite ends, so
  direction is not the answer and nothing currently is. A term-level replay over
  a grid of weights would settle it against the corpus already on disk.

**Two are held rather than planned.**

- **The counterexample arm, rerun on the fixed script (~4.2 h).** The
  per-board reading was withdrawn when the sweep turned out never to have varied
  its seed; the board question reopened at **Fisher p = 0.07 one-sided**, which
  is suggestive and not settled. See
  [the write-up](docs/findings/counterexample-is-the-sampler-not-the-board.md).
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
