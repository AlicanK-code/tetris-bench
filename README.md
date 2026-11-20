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

Milestones 1-6 of 8 complete: the engine, baseline agents, rendering and run
records, the model client, the sandboxed strategy agent, and the improvement
loop, with 502 unit tests.

| # | Milestone | State |
|---|-----------|-------|
| 1 | Engine (pieces, rotation, collision, line clears, 7-bag, legal placements) | **done** |
| 2 | Baselines (random + hand-written heuristic agent) | **done** |
| 3 | Rendering + metrics | **done** |
| 4 | Model client (OpenAI-compatible, local + cloud) | **done** |
| 5 | Strategy agent + sandbox | **done** |
| 6 | Improvement loop | **done** |
| 7 | Direct agent | not started |
| 8 | Analysis (curves, ladder gap, tokens/seconds per point) | not started |

## Setup

Requires [uv](https://docs.astral.sh/uv/); uv supplies Python itself, pinned to
3.13 in `.python-version`.

```bash
uv sync
uv run pytest
uv run ruff check . && uv run ruff format .
```

Milestone 8 needs the analysis extras: `uv sync --extra analysis`.

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
  piece has nowhere to land) or `piece_limit`, default 500. A competent
  heuristic stacks cleanly more or less forever, so without a cap a run would
  never finish; capping pieces rather than wall-clock time also keeps every
  model's game the same length.

Line scores are the classic 100 / 300 / 500 / 800 for 1-4 rows, with no level
multiplier since there is no gravity to speed up.

## Reference baselines

Three reference players, all at the default 500-piece budget. These are what the
LLM agents get measured against.

| agent | what it does | mean score | mean pieces |
|-------|--------------|-----------:|------------:|
| random | uniform over legal placements | 0 | 24 |
| naive | drops each piece as deep as it will go | 1,675 | 83 |
| heuristic | El-Tetris weights, 1-ply | **21,450** | **500** |

Per seed:

| agent | seed | pieces | lines | score | final holes | avg height | ended by |
|-------|-----:|-------:|------:|------:|------------:|-----------:|----------|
| random | 1 | 23 | 0 | 0 | 81 | 11.6 | block_out |
| random | 2 | 25 | 0 | 0 | 91 | 14.1 | block_out |
| random | 17 | 25 | 0 | 0 | 88 | 13.2 | block_out |
| random | 123 | 25 | 0 | 0 | 93 | 13.3 | block_out |
| naive | 1 | 95 | 21 | 2,100 | - | - | block_out |
| naive | 2 | 55 | 5 | 500 | - | - | block_out |
| naive | 17 | 111 | 28 | 2,800 | - | - | block_out |
| naive | 123 | 72 | 12 | 1,300 | - | - | block_out |
| heuristic | 1 | 500 | 197 | 21,600 | 2 | 6.9 | piece_limit |
| heuristic | 2 | 500 | 198 | 21,200 | 1 | 4.0 | piece_limit |
| heuristic | 17 | 500 | 195 | 21,200 | 4 | 4.8 | piece_limit |
| heuristic | 123 | 500 | 194 | 21,800 | 5 | 5.3 | piece_limit |

The random agent never clears a single line before dying, which makes it a floor
rather than a competitor. The heuristic reaches the piece budget on every seed
with 1-5 holes and an average stack height under 7 -- it is not dying, it is
being stopped by the cap, so the cap is what bounds the score.

Reproduce any row with:

```bash
uv run tetris-bench play --agent heuristic --seed 1
```

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

**Weights are a frozen dataclass**, defaulting to the published El-Tetris values,
so weight sets can be compared in one run without editing source.

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
uv sync --extra llm
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
floating-point non-associativity is, and no seed removes it. The 14B *is*
reproducible. Reproducibility is a property of the (model, prompt) pair and is
measured per rung -- see [docs/findings/](docs/findings/). The engine itself is
provably deterministic; this is entirely model-side.

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

To follow, once there are any.
