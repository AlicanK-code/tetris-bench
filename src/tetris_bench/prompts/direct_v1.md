You are playing Tetris. Choose where to put the current piece.

## Your task

Below is the board, the current piece, and every legal move for that piece,
numbered. Pick the one you want and reply with **its number and nothing else**.

You are choosing a *final resting place*, not steering a falling block. There is
no gravity timing and no soft drop: the piece goes straight to the position
described and locks there. There is also no hold piece.

## Reading the board

**Row 0 is the top of the board** and row {last_row} is the floor, so a piece
falling means its row index increases. A column is "tall" when filled cells
reach a low row index.

`#` is a filled cell and `.` is empty. The board is {width} columns wide and
{height} rows tall.

## The current position

```
{state}
```

## Your choices

Each line is `index  rot=R col=C lands row L`. `rot` is the orientation, `col`
is the leftmost column the piece would occupy, and `lands row L` is the lowest
row the piece touches once it has fallen -- a larger L means a deeper move.

```
{placements}
```

## Output format

Reply with a single integer between 0 and {last_index} inclusive: the index of
the move you choose. No explanation, no punctuation, no code block.

For example, if you wanted the first move in the list, the entire reply would
be:

```
0
```

A reply with no number in it, or a number outside that range, is recorded as an
invalid output and the engine plays move 0 instead -- which is an arbitrary
move, not a good one, so a malformed answer costs you the turn.
