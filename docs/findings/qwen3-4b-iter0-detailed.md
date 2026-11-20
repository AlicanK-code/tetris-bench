# Finding: qwen3-4b, strategy mode, iteration 0

**Date:** 2026-11-19
**Model:** `qwen3:4b` via Ollama 0.40.16, OpenAI-compatible endpoint
**Prompt:** `strategy_v1`
**Seed:** 1 · **Piece budget:** 500 · **Per-call budget:** 1.0s
**Artifacts:** `runs/functions/qwen3-4b-seed1-iter0.py`, `.json`

This is the first real model-written scoring function the benchmark has run. It
is recorded in full because it turns out to be a clean, measurable example of a
specific failure mode, and because iteration 0 is the baseline every later
iteration gets compared against.

---

## 1. Headline result

| measure | value |
|---|---|
| score | **0** |
| lines cleared | 0 |
| pieces placed | 22 |
| ended by | `block_out` |
| final holes | 107 |
| average holes | 50.1 |
| final max height | 20 |
| average max height | 15.6 |
| sandbox failures | **0** |
| model calls | 1 |
| tokens in / out | 649 / **9,091** |
| generation time | **325.1s** |
| throughput | ~28 output tokens/sec |
| cost | $0.00 |

### Against the reference players, same seed

| player | score | pieces | ended by |
|---|---:|---:|---|
| heuristic (Lee's 2013 weights) | 21,600 | 500 | piece_limit |
| naive (drop deepest) | 2,100 | 95 | block_out |
| **qwen3-4b iteration 0** | **0** | **22** | **block_out** |
| random | 0 | 23 | block_out |

Iteration 0 is **indistinguishable from random** in outcome, and marginally
worse in survival. It is far below the naive floor.

---

## 2. The function, verbatim

```python
def score(board, placement):
    stack_height = 0
    for row in range(20):
        if any(board[row][col] for col in range(10)):
            stack_height = row
    empty_cells = sum(1 for row in board for cell in row if not cell)
    return float(placement["lines_cleared"] * 10 + (100 - stack_height) + empty_cells * 0.1)
```

It is syntactically valid, passed the AST allowlist, loaded without error, and
raised on **zero** of its ~750 invocations. By every mechanical measure the
harness could apply, it worked.

---

## 3. Root cause: it is a constant function

Measured directly, the function returns **the same number for every candidate
placement**:

| board state | candidates | score range | distinct scores |
|---|---:|---|---:|
| empty board, piece S | 17 | 100.6 .. 100.6 | **1** |
| after 15 of its own moves | 12 | 94.6 .. 94.6 | **1** |

A scoring function that cannot distinguish between candidates provides no
signal. `max()` returns the first maximum, so the agent degenerates into "always
play the first legal placement" — the same behaviour the harness falls back to
when *every* placement fails to score. The score of 0 and death at 22 pieces are
the signature of that degenerate policy, not of a bad strategy.

### 3.1 Why `stack_height` is always 19

```python
for row in range(20):
    if any(board[row][col] for col in range(10)):
        stack_height = row
```

There is no `break`. The loop keeps reassigning on every occupied row, so
`stack_height` ends as the **lowest** occupied row index — the bottom of the
stack, not the top. The intent was plainly the opposite: the term
`(100 - stack_height)` only makes sense as "reward a low stack", which requires
the topmost occupied row.

Once anything rests on the floor — which is true from the first placement
onwards — row 19 is occupied, so `stack_height == 19` permanently.

Measured: `stack_height` took the value `19` for **every** candidate in both
positions sampled. The term contributes a constant `100 - 19 = 81`.

### 3.2 Why `empty_cells` is always constant

```python
empty_cells = sum(1 for row in board for cell in row if not cell)
```

This counts every empty cell on the board, including the open space above the
stack. Every tetromino fills exactly four cells, so for a fixed board and piece,
*every* candidate placement leaves the identical number of empty cells.

Measured: `196` for every candidate on the empty board (200 − 4). The term
contributes a constant `19.6`.

The count only changes when rows clear — which brings us to the third term.

### 3.3 Why `lines_cleared` never fires

`placement["lines_cleared"] * 10` is the one term that *could* vary, and it is
the only part of the function that is correct. But it only rewards a clear that
is already available on this move. Nothing in the function builds toward one, so
with the other two terms inert the agent plays arbitrarily, accumulates holes,
and never reaches a position where a line can complete. The game ended with
**0 lines cleared**, so this term contributed 0 throughout.

### 3.4 Composition

For any candidate, no lines clearing:

```
score = 0 * 10  +  (100 - 19)  +  196 * 0.1  =  0 + 81 + 19.6  =  100.6
```

Exactly the measured value.

---

## 4. The reasoning trace

The model reasoned for **35,138 characters / 6,245 words** (9,091 tokens) before
emitting a 337-character reply. Concept mentions in the trace:

| concept | mentions |
|---|---:|
| hole | 12 |
| bumpiness | 0 |
| flat / flatness | 0 |
| surface | 0 |
| overhang | 0 |
| topmost | 0 |
| aggregate | 0 |
| break (loop control) | 0 |

### 4.1 It identified holes, then defined them wrongly

> "Number of holes: Holes are empty spaces. More holes might mean the board is
> less stable."

That sentence contains the error. A hole in Tetris is a *covered* empty cell —
one with a filled cell somewhere above it in the same column. The model
collapsed "hole" into "empty space", then implemented the collapse as
`empty_cells`, which counts all empties and is therefore constant per move.

So the conceptual failure and the implementation failure are the same failure.
It is not that the model omitted holes; it is that it believed it had included
them.

### 4.2 It was briefly confused about board timing

The trace shows it working out whether `board` is pre- or post-placement:

> "Wait, the `board` is the state after the placement and clearing lines. [...]
> So the `lines_cleared` is already accounted for in the board."

It reached the right conclusion, but spent tokens getting there, and the second
half of that thought is wrong in a way that may have mattered: `lines_cleared` is
*not* redundant with the board, because the board shows the result of clearing
without recording that clearing happened. This is a candidate prompt-clarity
problem.

### 4.3 It never considered surface shape

Zero mentions of bumpiness, flatness, surface or overhangs. The entire class of
"is this stack shaped so that future pieces fit" was absent from its reasoning.

---

## 5. Final board

```
0123456789
##.#.##.#.
.########.
####....##
.#......#.
###.....##
##......##
##......#.
##......#.
##......#.
##......#.
.##.....#.
####...###
.#....###.
###...#...
#.....###.
###...##..
..#...###.
###...###.
.##....##.
##....##..
```

The left and right edges are piled to the ceiling while columns 3–6 are hollow —
the shape produced by repeatedly taking the first legal placement rather than
by any strategy. 107 holes.

### 5.1 Its choices were arbitrary, not bad

Mid-game, the 12 available candidates would have created between **71 and 98**
holes. The function picked the one creating **72**, which is near-optimal — by
pure accident, because it was first in the list. The best available was 71. The
agent is not choosing badly; it is not choosing at all.

---

## 6. What this tells us

### 6.1 The harness is sound

- AST validation accepted safe code and nothing was wrongly rejected.
- The sandbox executed ~750 calls with zero failures.
- The 500-piece game ran in under a second.
- The artifact and full reasoning trace were saved before the game played.
- Separately verified: the reference weights expressed through the sandbox's
  plain-data API score **byte-identically** to the in-process heuristic
  (21,600 / 21,200 on seeds 1 / 2), so the sandbox introduces no distortion.

The score of 0 is entirely attributable to the model.

### 6.2 Geometry-only was the right design decision

The gap between 0 and the 21,600 reference is the headroom an improvement curve
needs. Had the harness handed over precomputed features, iteration 0 would have
started near-competent and the curve would have been flat.

### 6.3 The 4B rung produces runnable output

The stated risk of geometry-only was that a 4B model would fail to write valid
code at all, yielding no curve. It did not. The code is valid and embodies two
specific, fixable errors — which is exactly the material an improvement loop acts
on.

### 6.4 This failure mode is invisible to the current harness

A constant scoring function and a well-reasoned-but-unlucky one produce the same
observable output: a low score. The harness reports `sandbox failures = 0`, which
is true and actively misleading — it suggests the function worked.

**This is the gap worth closing.** Measuring the spread of scores across
candidates would have made the diagnosis instant, and it is precisely the kind of
feedback Milestone 6 needs to put in front of the model.

### 6.5 Runtime planning for Milestone 6

325 seconds and 9,091 output tokens for one function, on the *smallest* rung.
Six iterations × four rungs × three seeds is on the order of 10–20 hours of
generation. The improvement loop needs checkpointing and resumability, not a
plain `for` loop.

---

## 7. Open questions

1. Does the hole/empty-cells conflation persist up the ladder, or is it
   4B-specific? Running `qwen3-30b` on the same seed answers this and determines
   whether the loop must teach the concept to every rung.
2. Would a prompt that warns a function must *discriminate* between candidates
   fix this without leaking strategy? The warning concerns function behaviour,
   not Tetris.
3. Should feedback name the bug class ("your function scored every candidate
   identically") or only the outcome ("you made 107 holes")? The former is a
   much stronger teaching signal; the latter is a purer test of the model's own
   diagnostic ability. This choice shapes what the benchmark measures.

---

## Addendum: what was changed in response (2026-11-19)

Two fixes, both aimed at §6.4 — the harness could not see this failure mode.

1. **Score-spread diagnostics** (`StrategyDiagnostics` in `agents/strategy.py`).
   The agent now records, per move, whether the function separated its candidates
   at all. A function that is flat on 95% or more of its moves is reported as
   `is_degenerate`, and the CLI prints an explicit note that a zero score means a
   dead function rather than a bad strategy. Verified on this exact function:
   `0/22 moves had score variation` versus the reference heuristic's
   `500/500, mean spread 6.83`.

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
