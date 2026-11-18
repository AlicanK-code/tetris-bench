# tetris-bench

A benchmark that measures how well LLMs **improve at Tetris across repeated attempts**,
not just how well they play once.

Each model plays the same seeded piece sequences, receives feedback on how it did, revises
its strategy, and plays again. The headline result is each model's **improvement curve**:
who learns fastest, who plateaus, and who regresses after a revision.

A secondary angle compares small local models (run on a MacBook) against frontier API
models, and asks whether the improvement loop narrows the gap.

## Status

Milestones 1-2 of 8 complete: the game engine and the baseline agents, with 205 unit
tests. No LLM code yet.

| # | Milestone | State |
|---|-----------|-------|
| 1 | Engine (pieces, rotation, collision, line clears, 7-bag, legal placements) | **done** |
| 2 | Baselines (random + hand-written heuristic agent) | **done** |
| 3 | Rendering + metrics | not started |
| 4 | Model client (OpenAI-compatible, local + cloud) | not started |
| 5 | Strategy agent + sandbox | not started |
| 6 | Improvement loop | not started |
| 7 | Direct agent | not started |
| 8 | Analysis (curves, gap, cost per point) | not started |

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

## Results

To follow, once there are any.
