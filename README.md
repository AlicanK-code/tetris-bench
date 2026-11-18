# tetris-bench

A benchmark that measures how well LLMs **improve at Tetris across repeated attempts**,
not just how well they play once.

Each model plays the same seeded piece sequences, receives feedback on how it did, revises
its strategy, and plays again. The headline result is each model's **improvement curve**:
who learns fastest, who plateaus, and who regresses after a revision.

A secondary angle compares small local models (run on a MacBook) against frontier API
models, and asks whether the improvement loop narrows the gap.

## Status

Milestone 1 of 8 complete: the game engine, with 139 unit tests. No LLM code yet.

| # | Milestone | State |
|---|-----------|-------|
| 1 | Engine (pieces, rotation, collision, line clears, 7-bag, legal placements) | **done** |
| 2 | Baselines (random + hand-written heuristic agent) | not started |
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

## Reference baseline

A deliberately naive policy -- "drop each piece as deep as it will go" -- buries
holes and blocks out well before the piece budget. It is the floor the
Milestone 2 heuristic agent has to beat:

| seed | pieces placed | lines | score | ended by |
|------|---------------|-------|-------|----------|
| 1    | 95            | 21    | 2100  | block_out |
| 2    | 55            | 5     | 500   | block_out |
| 17   | 111           | 28    | 2800  | block_out |
| 123  | 72            | 12    | 1300  | block_out |

## Results

To follow, once there are any.
