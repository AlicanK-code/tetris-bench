# The counterexample jump is the sampler, not the board

**Status:** replicated at n=15 distinct samples. The effect is real and it is
intermittent. The earlier "one success in three boards" reading was wrong.

## What was being tested

`analysis/counterexample_arm.py` shows the model a *trace board* — a snapshot
from a game its own function played — alongside the ordinary outcome feedback,
and asks for a revision. The control arm gets outcome feedback only.

The function being revised (`runs/functions/noise/qwen3-14b-noise1.py`) has the
project's signature defect: `heights[col] > row`, which has the board's
orientation backwards and so cannot see a gap. Iteration 0 scores **110** on the
held-out seeds, **3.8 points per piece**.

The first pass showed three boards once each and got held-out **2540 / 120 / 5**
for boards at piece 8 / 16 / 24. Read as a per-board effect, that says board 8
is informative and board 24 is actively harmful. That reading does not survive.

## The replication

Six boards (pieces 4, 8, 12, 16, 20, 24), three runs each, `qwen3-14b`,
2026-11-23 02:03–06:20 GMT, 4h16m, 18 generations at ~855s each.

| board | distinct samples (held-out score) | holes |
|---|---|---|
| 4  | 20, 40 | 99.5, 100.5 |
| 8  | **2455**, 130 | 37.6, 82.2 |
| 12 | 95, 145 | 91.3, 78.6 |
| 16 | 95, 105 | 88.2, 89.9 |
| 20 | 100, 100 | 85.7, 101.7 |
| 24 | 65, **5835** | 93.8, 22.9 |

Iteration 0 for comparison: score 110, holes 85.8.

**Board 24 produced both the worst result in the first pass (5) and the best
result in the project's history (5835).** Board 8 produced 2540 and 2455 on two
samples and 130 on two others. Which board is shown does not predict the
outcome; the sample does.

Counting all 15 distinct samples across both passes, **3 jumped by more than
20×** (2540, 2455, 5835) and the other 12 landed between 20 and 145 — at or
around the unrevised 110. So the intervention fires about **20% of the time**,
and when it fires it is decisive: 5835 is **33.1 points per piece** against
iteration 0's 3.8, within sight of the hand-written heuristic's 43.5.

## The mechanism, where it is visible

The holes column separates the two outcomes cleanly. Both big winners cut holes
from 85.8 to 37.6 and 22.9. Every other sample stayed at 78–102, i.e. it never
learned to see the gap at all, whatever it did to its weights.

Of the 12 distinct samples, 5 rewrote the `heights[col] > row` comparison and 7
left it verbatim. Both winners are in the group of 5; none of the 7 that kept
the line scored above 145. Fisher exact on 2/5 against 0/7 gives p=0.19, so this
is a direction and not a result — but it is the direction the mechanism predicts.
Changing the line is close to necessary; changing it *correctly* is the part the
model gets right one time in five or so.

## A sampling bug this surfaced

**Runs 11 and 12 produced byte-identical functions on all six boards** — same
hash, same output-token count. Run 10 always differed. So `--runs 3
--start-index 10` yielded two distinct samples per board, not three, and a
sixth of the 4h16m was spent regenerating work already done.

The seed derivation for consecutive run indices is collapsing somewhere between
the index and the request. Until that is found, **read n as two-thirds of the
`--runs` value** on this script, and check the hashes before trusting a count.

## What this changes

- The counterexample arm stays a live result: a trace board can take a function
  from 3.8 to 33.1 points per piece, which nothing in the outcome-only control
  has ever done (its two revisions scored 130 and 85 against 110).
- It cannot be reported as a reliable intervention. At ~20% it needs n per cell
  in the double digits before two conditions can be compared, which is ~5h of
  generation per cell on this hardware.
- Any future per-board claim needs n well above 3. The first pass is a worked
  example of how a 3-sample sweep invents structure that is not there.
