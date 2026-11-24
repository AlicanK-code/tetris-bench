# The best revision was a repair, and its predecessor was a lucky tie-breaker

**Date:** 2026-11-24 · **Models:** `qwen3-30b`, `qwen3-8b` · no GPU, term-level replay
**Sources:** [`runs/published/reweighting/`](../../runs/published/reweighting/) — 23 variants
**Method:** `analysis/reweighting.py`, a few minutes, no model calls

Two revisions in this corpus moved their weights the same qualitative direction
— hole penalty up, line reward down, *survive, do not chase lines* — and ended
in opposite places. `qwen3-30b` chain 1 went **41.55 → 50.19** points per piece,
the best function the project has. `qwen3-8b` chain 3 went **34.57 → 11.46**,
the worst collapse in its run, from the best opening function in it.

The 30B write-up credited that chain's success to the direction. The 8B run
produced the counterexample, and both documents then recorded the same open
question: *what separates a good reweighting from a fatal one, given both moved
the same way?*

**The question was built on a false premise. Neither revision was what it looked
like, and the shared direction helped in both cases.**

---

## 1. Method: each function is its own baseline

Hold a function's structure fixed, change only its numeric weights, replay on
the ten held-out seeds. Nothing then depends on the four rungs computing their
terms the same way, which they emphatically do not — one of the two functions
here measures height by counting filled cells and the other by finding the
topmost one.

Where a revision changed more than its weights, the changes are **crossed**, so
each can be measured with the others held fixed. Where only the weights changed,
each weight is walked **one at a time** from its old value to its new one, which
a single before-and-after number cannot do.

Both reconstructions were validated against the originals before anything was
concluded from them: the cell standing in for iteration 0 scores **41.55** and
the one standing in for iteration 5 scores **50.19**, matching the saved
functions exactly.

---

## 2. The 30B's revision changed three things, not one

Iteration 0 computed its column heights like this, verbatim:

```python
for row in range(19, -1, -1):        # scanning UP from the bottom
    if board[row][col]:
        lowest_filled = row
        break
heights.append(19 - lowest_filled)
```

**Row 0 is the top.** For any column resting on the floor the first filled cell
found is row 19, so the height is `19 - 19 = 0`. Every height is zero, which
makes `max_height` and `bumpiness` **both dead** — and the capability probes
already recorded exactly that, classifying iteration 0 as `height: blind` and
**not strategy-capable**. Iteration 5 scans down from row 0 and is correct.

So the revision repaired two terms, reweighted the four, *and* dropped a
trailing tie-breaker iteration 0 had carried. Crossing all three:

| heights | weights | tie-breaker | pts/piece | pieces | tied at max |
|---|---|---|---:|---:|---:|
| dead | old | yes | **41.55** | 2,457 | 0% |
| dead | old | no | 15.29 | 543 | 55% |
| dead | new | yes | 37.65 | 1,312 | 0% |
| dead | new | no | 17.14 | 566 | 53% |
| live | old | yes | 44.81 | 8,994 | 0% |
| live | old | no | 44.63 | 9,439 | 11% |
| live | new | yes | 50.72 | 20,000 | 0% |
| live | new | no | **50.19** | 18,164 | 12% |

Taking iteration 0 as the real baseline — tie-breaker present, because it was:

| | |
|---|---:|
| repair alone, weights unchanged | **+3.25** |
| reweighting alone, heights still dead | **−3.90** |
| both together | **+9.16** |
| **interaction** | **+9.81** |

**The reweighting alone makes the function worse.** Its new weights are good
only on a repaired function: on the broken one they cost 3.90 points, and on the
repaired one they are worth +5.91. The interaction is larger than either main
effect, which is the formal way of saying that neither change explains the
outcome by itself.

That resolves the question for this half. The 30B's chain 1 is **a capability
repair**, which is the one thing [this project has already shown the loop
does](the-loop-does-not-repair-capability.md) — and it is in fact one of the
three repairs that run's own probe data recorded. The 30B write-up counted it as
a repair in one section and credited it to reweighting in another, and never
connected the two.

---

## 3. And iteration 0 was mostly an accidental heuristic

The row that should not be ignored in that table: with its tie-breaker removed,
iteration 0 scores **15.29**, not 41.55. A term the model appended to make its
scores unique —

```python
unique_term = (placement["row"] * 10 + placement["column"]) * 0.001
```

— worth at most 0.199 against terms scaled in hundreds, is carrying **26.26 of
its 41.55 points per piece, 63% of the total.**

The mechanism is in the last column. With its height terms dead the function is
`lines * 100 - holes * 20`, which separates candidates whenever they differ in
holes or lines and ties whenever they do not: **55% of its decisions were ties
at the maximum**, so more than half the time the tie-breaker was not breaking a
tie, it *was* the policy. On the repaired function that falls to 11%, and the
same term is worth +0.17.

And the tie-breaker is not arbitrary. `placement["row"]` is the top row of the
piece's bounding box, and row 0 is the top, so a larger row is a **lower**
placement:

| trailing term | pts/piece | tied at max |
|---|---:|---:|
| none | 15.29 | 55% |
| `(row*10 + column) * 0.001` — as written | **41.55** | 0% |
| `row * 0.001` — prefers low | **42.88** | 25% |
| `-row * 0.001` — prefers high | **13.92** | 14% |
| `column * 0.001` — breaks ties, no height information | 22.46 | 2% |

Breaking ties at all is worth **+7.17**. Preferring *low* placements is worth a
further **+20.42**, and preferring high is worse than not breaking ties at all.
The model wrote a uniqueness hack and accidentally encoded *place the piece as
low as possible*, which on a function blind to height was the only real strategy
it had.

---

## 4. The 8B's collapse was not the lines-and-holes move

Here only the weights changed — both endpoints compute their terms identically,
and iteration 5's extra `bottom_empty` term counts all-empty rows upward from
row 19 and stops at the first non-empty one, so it is zero on any board resting
on the floor. Both ends are probe-clean. Walking each weight from its old value
to its new one, one at a time:

| weight moved | from → to | pts/piece | Δ |
|---|---|---:|---:|
| *(iteration 0 itself)* | | 34.57 | |
| `lines` | 100 → 50 | 34.57 | **+0.00** |
| `holes` | 1 → 100 | **41.02** | **+6.44** |
| `max_h` | 0.5 → 150 | 16.23 | **−18.34** |
| `unevenness` | 0.1 → 150 | 5.44 | **−29.14** |

**The part that matched the 30B's direction is the part that helped.** Raising
the hole penalty a hundredfold gained 6.44 points per piece on its own, and
halving the line reward changed nothing measurable. The collapse came entirely
from the two surface terms, which iteration 5 set to 150 each — three times a
line clear and 1.5 times a hole.

Reverting one weight at a time from iteration 5 agrees:

| weight reverted | to | pts/piece | Δ |
|---|---|---:|---:|
| *(iteration 5 itself)* | | 11.46 | |
| `unevenness` | 0.1 | **26.60** | **+15.14** |
| `lines` | 100 | 12.25 | +0.79 |
| `max_h` | 0.5 | 8.93 | −2.53 |
| `holes` | 1 | 7.45 | −4.01 |

Undoing the unevenness weight alone recovers more than half the lost ground.
Undoing the hole weight makes things *worse*, which is the same result from the
other end: by iteration 5 the hole penalty had become load-bearing.

The function iteration 5 describes will not accept a line clear if it raises or
roughens the stack, and on a ten-wide board that is most line clears. It is not
a function that chased lines too little; it is one that would not build at all.

---

## 5. What this answers, and what it costs the record

**The open question is closed, and dissolved rather than answered.** "Same
direction, opposite outcome" was a description of neither revision:

- the 30B's gain was **a repair**, whose reweighting is worth −3.90 without it;
- the 8B's loss came from **its height and unevenness weights**, while its
  lines-and-holes move gained +6.44.

The hole-penalty direction helped on both rungs. There is no longer a puzzle
about a direction producing two outcomes, because it did not.

Three published claims change, and all three move the same way — toward the
project's existing headline rather than away from it:

1. **"The project's only clean example of a revision getting a weighting
   right"** is withdrawn. It is an example of a revision repairing a broken term
   and then weighting it, which is repair, not refinement.
2. **"The best result came out of the loop"** still stands — iteration 5 is
   genuinely the best function here, and the loop genuinely produced it — but
   the mechanism is now the one the project already documented, and the +8.64
   remains inside a σ_d of 16.76 either way.
3. **Iteration 0's 41.55 was 63% tie-breaker.** Any reading of it as a strong
   first attempt, or of the 30B rung as arriving near the heuristic cold, needs
   that caveat. The rung's *repaired* function reaches 44.63 on iteration 0's own
   weights, so the capability was there; the published 41.55 was not measuring
   it.

**What it does not do** is explain why either model made the edit it made. The
30B repaired a term it was never told was broken, from outcome feedback alone,
which is the most interesting single event in this corpus and rests on one
chain. Nothing here says it was anything but luck.

**Still open, and now sharper:** on both rungs the hole penalty was
under-weighted at iteration 0 and the surface terms were the dangerous ones. A
grid over those two weights on a repaired structure would say whether there is a
single ridge both models were walking along, which is a cheap next step against
the same corpus.

---

## 6. Reproducing it

```bash
uv run python analysis/reweighting.py
```

Every variant it replays is written to
[`runs/published/reweighting/`](../../runs/published/reweighting/) so the
numbers can be checked against source. The two reconstructions should read
41.55 and 50.19; if they do not, the variants no longer match the originals and
nothing above should be trusted.

The designs and their arithmetic are in `src/tetris_bench/reweighting.py`,
unit-tested in `tests/test_reweighting.py` — including the interaction formula,
whose sign is the whole conclusion of §2.
