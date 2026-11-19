# Finding (summary): qwen3-4b writes a constant scoring function

**2026-11-19 · `qwen3:4b` · strategy mode · prompt `strategy_v1` · seed 1**
Full version: [`qwen3-4b-iter0-detailed.md`](qwen3-4b-iter0-detailed.md)

## In one line

The model wrote valid, safe, non-crashing code that returns **the same score for
every candidate move**, so the agent played arbitrarily and scored 0.

## The numbers

| player, seed 1 | score | pieces | holes | ended by |
|---|---:|---:|---:|---|
| heuristic reference | 21,600 | 500 | 2 | piece_limit |
| naive floor | 2,100 | 95 | — | block_out |
| **qwen3-4b, iteration 0** | **0** | **22** | **107** | **block_out** |
| random | 0 | 23 | 81 | block_out |

Cost: 1 call, 649 tokens in, **9,091 out**, **325s**, $0.00.
Sandbox failures: **0**.

## What it wrote

```python
def score(board, placement):
    stack_height = 0
    for row in range(20):
        if any(board[row][col] for col in range(10)):
            stack_height = row
    empty_cells = sum(1 for row in board for cell in row if not cell)
    return float(placement["lines_cleared"] * 10 + (100 - stack_height) + empty_cells * 0.1)
```

## Why it scores 0

Measured: **score range 100.6 .. 100.6 across all 17 candidates.** One distinct
value. Two of the three terms are constant by construction:

- **`stack_height` has no `break`**, so it finds the *lowest* occupied row, not
  the topmost. Once anything rests on the floor it is permanently 19.
- **`empty_cells` counts every empty cell**, and every piece fills exactly four,
  so it is identical for all candidates of a given move.
- **`lines_cleared`** is correct but never fires, because nothing in the function
  builds toward a clear.

With no signal, `max()` takes the first candidate every time — the agent
degenerates into "always play the first legal placement".

Its choices were *arbitrary, not bad*: mid-game, available moves created 71–98
holes and it took one creating 72, by accident of ordering.

## The interesting part

Its reasoning ran 6,245 words and **named holes as a factor** — then defined them
wrongly:

> "Number of holes: Holes are empty spaces."

A hole is a *covered* empty cell. It implemented that misdefinition as
`empty_cells`. So it believed it had accounted for holes. It never mentioned
bumpiness, surface shape or overhangs at all.

## What it establishes

1. **The harness is sound.** Zero sandbox failures, nothing wrongly rejected, and
   El-Tetris through the same sandbox scores byte-identically to the in-process
   heuristic. The 0 is the model's.
2. **Geometry-only was right.** The gap from 0 to 21,600 is the headroom an
   improvement curve needs; precomputed features would have flattened it.
3. **The 4B rung is usable.** It produces valid code with specific, fixable
   errors — the exact material an improvement loop acts on.
4. **The harness cannot currently see this failure.** It reports
   `sandbox failures = 0`, which is true and misleading. Measuring score spread
   across candidates would diagnose it instantly.
5. **Milestone 6 needs checkpointing.** 325s per function on the smallest rung
   means a full run is 10–20 hours.

## Next questions

- Does the hole/empty-cells conflation persist on `qwen3-30b`, or is it
  4B-specific?
- Should feedback name the bug class ("every candidate scored the same") or only
  the outcome ("107 holes")? The first teaches; the second tests the model's own
  diagnostic ability. This choice shapes what the benchmark measures.

---

## Addendum: what was changed in response (2026-11-19)

Two fixes, both aimed at §6.4 — the harness could not see this failure mode.

1. **Score-spread diagnostics** (`StrategyDiagnostics` in `agents/strategy.py`).
   The agent now records, per move, whether the function separated its candidates
   at all. A function that is flat on 95% or more of its moves is reported as
   `is_degenerate`, and the CLI prints an explicit note that a zero score means a
   dead function rather than a bad strategy. Verified on this exact function:
   `0/22 moves had score variation` versus El-Tetris's `500/500, mean spread 6.83`.

2. **Prompt `strategy_v2`.** `strategy_v1` is kept on disk so this run's prompt
   stays readable. v2 adds two things, both about mechanics rather than Tetris:
   that a function's scores *must differ between candidates* or the engine cannot
   choose, with a nudge to check each term actually varies; and that
   `lines_cleared` is not recoverable from `board`, which the trace shows the
   model concluded wrongly.

**Deliberately not changed:** the prompt still does not define holes, mention
bumpiness, or supply any feature helpers. Fixing the model's misdefinition of
"hole" would hand over the concept whose discovery is the thing being measured.
Whether to cross that line is an open design decision, not an oversight.
