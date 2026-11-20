You wrote a Python scoring function to play Tetris. It has been played, and this
is how it went. Revise it.

{feedback}

## The function you wrote

```python
{previous_source}
```

## Your task

Write an improved version. Same signature, same rules as before:

```python
def score(board, placement):
    ...
```

The engine calls it once for every legal placement of the current piece and plays
whichever scores **highest**. Higher is better. Your function must give different
candidates different scores, or the engine has nothing to choose on.

`board` is the board the placement **would produce** - after the piece locks and
after any completed rows clear. It is a tuple of {height} rows, each a tuple of
{width} booleans, where `True` means filled. **Row 0 is the top** and row
{last_row} is the floor, so a falling piece's row index increases.

`placement` is a dict with `kind`, `rotation`, `column`, `row`, `cells` and
`lines_cleared`. `lines_cleared` is not recoverable from `board`, since the board
already reflects the clearing.

Rules: no imports (`math` is already available as a name), no file, network or
system access, return an `int` or `float`, and each call must finish within
{per_call_seconds} seconds. A placement whose scoring raises or times out is
treated as unplayable and never chosen.

## Output format

Reply with **one Python code block and nothing else**. No explanation before or
after it. You may keep whatever worked, change whatever did not, and restructure
freely - it does not have to resemble your previous attempt.
