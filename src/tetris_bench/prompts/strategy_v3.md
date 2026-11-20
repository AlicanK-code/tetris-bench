You are writing a Python function that plays Tetris by scoring candidate moves.

## Your task

Write a function with exactly this signature:

```python
def score(board, placement):
    ...
```

The engine will call it once for every legal placement of the current piece and
play whichever one scores **highest**. Higher is better. Return a single number.

**Your function must give different candidates different scores.** That is how
the engine chooses. If it returns the same number for every candidate, the engine
has nothing to go on and simply plays the first move in the list, which loses
quickly. Before you finish, check that each term you use actually *varies*
between one candidate placement and another — a term that is the same for all of
them contributes nothing, however sensible it looks.

## What you are given

`board` is the board the placement **would produce** - after the piece has
locked and after any completed rows have been cleared. It is a tuple of
{height} rows, each a tuple of {width} booleans. `True` means the cell is
filled.

**Row 0 is the top of the board** and row {last_row} is the floor, so a piece
falling means its row index increases. A column is "tall" when filled cells
reach a low row index.

`placement` is a dict:

| key | meaning |
|-----|---------|
| `kind` | the piece letter: one of I, O, T, S, Z, J, L |
| `rotation` | which orientation was used |
| `column` | leftmost column of the piece |
| `row` | topmost row of the piece after it landed |
| `cells` | tuple of `(row, column)` pairs the piece occupies |
| `lines_cleared` | how many rows this placement completed, 0 to 4 |

`lines_cleared` is **not** recoverable from `board`. The board shows the result
*after* clearing, so a board that had two rows removed looks much like one that
never filled them. If you care whether a move cleared rows, read
`lines_cleared`.

## Rules your code must follow

- **No imports.** `math` is already available as a name - use `math.sqrt(...)`
  directly, with no import statement.
- No file, network or system access. Those names do not exist in your namespace.
- Return an `int` or `float`. Returning a string, `None`, a bool or `NaN` counts
  as a failure for that placement.
- You may define helper functions above `score`.
- Each call must finish within {per_call_seconds} seconds. Avoid unbounded loops.
- Any placement whose scoring raises or times out is treated as unplayable and
  will never be chosen, so a bug costs you moves.

{measurement_section}
{feedback_section}
## Output format

Reply with **one Python code block and nothing else**. No explanation before or
after it.

```python
def score(board, placement):
    return float(placement["lines_cleared"])
```

That example is a deliberately poor strategy - it clears a line when it can and
is otherwise indifferent, so it stacks blindly and dies quickly. It is there to
show the shape of an answer, not the content of a good one.

## What makes a good scoring function

That is for you to work out. You have the full board, so you can measure
anything you can compute from it. Think about what makes a Tetris position
survivable several moves later, not just what scores now.
