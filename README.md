# tetris-bench

A benchmark that measures how well LLMs **improve at Tetris across repeated attempts**,
not just how well they play once.

Each model plays the same seeded piece sequences, receives feedback on how it did, revises
its strategy, and plays again. The headline result is each model's **improvement curve**:
who learns fastest, who plateaus, and who regresses after a revision.

A secondary angle compares local models of increasing size -- a capability ladder
from roughly 4B to 30B, all on one MacBook -- and asks whether the improvement
loop lets a small model close on a larger one.

**Everything runs locally; no paid APIs.** The client supports cloud providers and
that path is tested, but no planned run uses one. Dollar cost is therefore always
zero, so the headline cost measures are tokens and wall-clock seconds.

## Status

The engine, baseline agents, rendering and run records, the model client, the
sandboxed strategy agent, the improvement loop and the analysis all work, under
591 unit tests. What is not finished is the measurement: see
[Results](#results) for what is established and what is still running.

| # | Milestone | State |
|---|-----------|-------|
| 1 | Engine (pieces, rotation, collision, line clears, 7-bag, legal placements) | **done** |
| 2 | Baselines (random + hand-written heuristic agent) | **done** |
| 3 | Rendering + metrics | **done** |
| 4 | Model client (OpenAI-compatible, local + cloud) | **done** |
| 5 | Strategy agent + sandbox | **done** |
| 6 | Improvement loop | **done** |
| 7 | Direct agent | cut to a demonstration, see [Results](#results) |
| 8 | Analysis (curves, ladder gap, tokens/seconds per point) | **done**; the ladder has no data yet |

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
`score(board, placement) -> float` function, so a sandboxed model-written scorer
drops into the same slot as the hand-written heuristic, driven by the same
adapter -- no parallel code path, and an apples-to-apples comparison for free.
`Agent` stays the general interface, since "choose uniformly at random" is not a
per-placement rating.

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
back for feedback snapshots and debugging.

**Legal moves are offered as a numbered list**, and a model answers with an
index:

```
 0  rot=0 col=0 lands row 15
 1  rot=0 col=1 lands row 15
 2  rot=0 col=2 lands row 18
```

Choosing from a list it was handed cannot produce an illegal move, whereas
describing one freely can -- and an invalid output is a wasted call plus a row in
the failure column.

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

**Temperature defaults to 0, and a seed is set -- but neither makes generation
reproducible.** Measured: two runs of a byte-identical prompt at temperature 0
with a fixed seed produced different functions on the 4B and on the 30B, where
the two scored 0 and 1,700. The seed is honoured, so sampling is not the cause;
floating-point non-associativity is, and no seed removes it. Reproducibility is
a property of the (model, prompt) pair and is measured per rung -- see
[docs/findings/](docs/findings/). The engine itself is provably deterministic;
this is entirely model-side.

**The temperature-0 default is also why `--chains` needs overriding.** Greedy
decoding takes the argmax at every step and never draws from the RNG, so a
per-chain seed has no random number to index: measured, three seeds at
temperature 0 return one byte-identical generation, and at 1.0 return three
different ones. A multi-chain sweep at temperature 0 therefore draws **one**
sample and pays N times for it -- which a five-chain run discovered the
expensive way, with four of its five chains byte-identical. The `qwen3-14b`
entry sets `temperature: 0.7` for this reason, and the cost is smaller than it
looks: a *fixed* seed still gives bit-identical output there, so reproducibility
moves from `prompt -> output` to `(prompt, seed) -> output`, and the former was
already unavailable on this rung regardless.

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

All figures below are `qwen3:14b` in `strategy` mode, read from **held-out**
seeds the model never saw outcomes for, at zero dollars.

### The improvement curve exists, and so does the regression

One chain, six iterations, mean score over 10 unseen seeds:

| iteration | held-out score | pieces | what changed |
|----------:|---------------:|-------:|--------------|
| 0 | 20 | 15 | first attempt, inverted height signs |
| 1 | 2,290 | 98 | reweighted, did not debug |
| 2 | 2,130 | 93 | reweighted again |
| 3 | 470 | 52 | inverted heights *and* minus signs |
| 4 | **25,180** | **626** | flipped the signs to plus |
| 5 | 6,850 | 185 | "fixed" the definition, broke three terms |

20 to 25,180 over four revisions is a real gain, and so is the 73% fall that
follows the peak. Whole run: 51,627 tokens, 4,121 seconds, **$0**.

**Read this curve with the caveat the tooling prints itself.** It is one chain,
so it cannot see generation noise, and `curves.py` says so: *"one chain cannot
see generation noise, so the bar above is known to be too lenient."* Generation
noise is demonstrably large -- two runs of an identical iteration-0 prompt
scored 1,580 and 20. A five-chain sweep is what settles whether "this model
improves" is a claim this benchmark can make; until it finishes, the defensible
results are the mechanisms below.

### The strongest result is a credit-assignment failure

Verified by replaying the saved functions, not inferred from the scores:

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

Iteration 4 against the hand-written heuristic, on the same held-out seeds:

| | points/piece | pieces survived |
|---|---:|---:|
| heuristic (Lee 2013) | 43.5 | 10,467 |
| best model function | 40.2 | 626 |

**About 92% of the heuristic's scoring rate, and 6% of its survival.** The model
learned to clear lines about as efficiently as a tuned hand-written heuristic
and never learned to stay alive. Quoting totals alone would have called this
"69% of the heuristic" and hidden both halves -- see
[Reference baselines](#reference-baselines).

```bash
uv run python analysis/baseline_ceiling.py --max-pieces 50000 --seeds 20
```

### Findings with their own write-ups

Each of these is a separate experiment in [docs/findings/](docs/findings/), with
the generated functions as artifacts:

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

### Not done

- **The five-chain sweep** that decides whether the curve survives generation
  noise. Running.
- **The capability ladder.** Only the 14B has ever been through the loop; 4B, 8B
  and 30B are configured and unrun, so the "does a small model close on a large
  one" question has no data.
- **Milestone 7, the direct agent**, cut to a planned demonstration rather than
  a full arm: a model call per turn at ~500 turns per game is enormous for a
  result the prior work already reports, so one short game to show the failure
  mode and the cost ratio is the whole value.
The artifacts behind every finding above *are* in the repo, under
[`runs/published/`](runs/published/) -- the generated functions plus the prompt,
reasoning trace and raw reply that produced each one, so the claims can be
checked rather than taken on trust. Working output stays gitignored.

## Licence

[MIT](LICENSE). The heuristic baseline weights are from Yiyuan Lee's 2013 post,
credited in [Agent design notes](#agent-design-notes).
