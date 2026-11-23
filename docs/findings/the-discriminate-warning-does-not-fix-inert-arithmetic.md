# The discriminate warning does not fix inert arithmetic

**Date:** 2026-11-23 · **Models:** all four rungs · no GPU, sandbox replay
**Corpus:** 134 published generations, 125 of which load and run
**Question:** open question 2 of
[the 4B iteration-0 study](qwen3-4b-iter0-detailed.md) — "would a prompt that
warns a function must *discriminate* between candidates fix this without leaking
strategy?"

The leakage half was settled by construction: the warning talks about function
behaviour, not Tetris. This document answers the other half as far as the corpus
allows, which is **less far than the question assumed**, and turns up a
measurement trap on the way.

---

## 1. The warning, and who received it

`strategy_v1` does not carry it. `strategy_v2` added it and `strategy_v3` keeps
it, bolded, with an actionable second half:

> **Your function must give different candidates different scores.** That is how
> the engine chooses. If it returns the same number for every candidate, the
> engine has nothing to go on and simply plays the first move in the list, which
> loses quickly. Before you finish, check that each term you use actually
> *varies* between one candidate placement and another.

**Of 134 published generations, 132 received it and 2 did not.** The two are
`qwen3-4b-seed1-iter0` and `qwen3-4b-seed1-strategy_v1`, from the original
prompt-comparison arm — one model, one seed.

So the comparison the open question asked for — the degenerate rate under v2
against v1 — has **n = 2 on one side**. It cannot be a rate, and no amount of
analysis of this corpus will make it one.

---

## 2. What can be measured: inert functions persist under the warning

Every published function was replayed in the sandbox against eight boards
(seeds 1, 2 and 17 at depths 0, 8 and 20; boards with fewer than two legal
placements excluded), and classified by whether it ever returns a different
number for a different candidate.

| rung | ran | constant on **every** board | constant on some |
|---|---:|---:|---:|
| `qwen3-4b` | 43 | **5** | 20 |
| `qwen3-8b` | 13 | 0 | 9 |
| `qwen3-14b` | 54 | 0 | 15 |
| `qwen3-30b` | 15 | **0** | **0** |

**Five of 125 functions are inert on every board, and all five are 4B.** Three
of those five were written *under* the warning. So the warning does not
eliminate the failure it describes: it is still produced, at roughly 2.4% of
warned generations (3 of 123) and 12% of warned 4B generations.

**The 30B is the only rung with no flatness anywhere** — 15 of 15 return
different numbers for different candidates on all eight boards.

### The one controlled pair says the warning did not fix it

The prompt-comparison arm produced exactly one v1/v2 pair on the same model and
seed. Both members are **constant on every board**:

| generation | prompt | verdict |
|---|---|---|
| `qwen3-4b-seed1-strategy_v1` | no warning | inert on all 8 boards |
| `qwen3-4b-seed1-strategy_v2` | **warned** | inert on all 8 boards |

That is n = 1 and settles nothing on its own. But it is the only direct evidence
available, and it points at "no effect" rather than at the fix the question
hoped for.

---

## 3. The measurement trap, which is the transferable part

A naive version of this probe — "does the function return the same number for
every candidate on a board?" — **over-reports by about five times**, because on
a near-empty board many placements are genuinely equivalent and a *correct*
function returns equal scores for them.

Flat rate per board, over the same 125 functions:

| board | candidates | returned one value for all |
|---|---:|---:|
| seed 1, empty | 17 | **36 (29%)** |
| seed 2, empty | 34 | 7 (6%) |
| seed 17, empty | 34 | 7 (6%) |
| seed 1, depth 8 | 34 | 6 (5%) |
| seed 2, depth 8 | 17 | 6 (5%) |
| seed 17, depth 8 | 17 | 6 (5%) |
| seed 1, depth 20 | 7 | 25 (20%) |
| seed 2, depth 20 | 7 | 12 (10%) |

The 29% on the first row is mostly not a defect. An I-piece on an empty board
has placements that differ only by translation, so a function measuring height,
holes and bumpiness *should* score them identically. The depth-20 rows are
inflated for the opposite reason — only 7 candidates, so a tie is likelier by
chance.

**Only "constant on every board" is a defensible defect**, and the per-board
rates are what a single-board probe would have reported instead. The earlier
`flat_moves` figures in the run records do not have this problem, because they
aggregate across a whole game, but any future probe does.

---

## 4. What `flat_moves` was telling us, and what it was not

The run records carry `flat_moves`, and across all 127 played positions only
five register as *fully* flat: `4b-loop` chain 3, iterations 1 to 5.

Those are not inert arithmetic. They are
[the crash chain](4b-loop-reweights-a-crash-five-times.md) — every scoring call
raised `UnboundLocalError`, and a function that crashes separates nothing, so it
counts as flat. The sandbox returns `-inf` for a failed call, which is also why
a first pass of this analysis read them as "constant": **`-inf` is the failure
sentinel, not a score**, and has to be excluded before testing for constancy.

So `flat_moves` conflates "returned a constant" with "failed on every call".
That is defensible for the purpose it was added for — both mean the engine had
nothing to choose on — but it means **`flat_moves` cannot answer this question**,
and the sandbox replay above is the right instrument.

---

## 5. Verdict

**Answered, negatively and with a stated limit.** Inert functions are still
produced under the warning — 3 of 123 warned generations, all on the 4B — and in
the single controlled v1/v2 pair the warned member is inert too. The warning
does not fix the failure.

**Not answered:** whether it *reduces* the rate. That needs a real v1 arm, and
at a 2.4% base rate under v2 a comparison powered to detect even a halving would
need hundreds of generations per side. Like the zeros rate, this is a question
the existing design cannot settle rather than one nobody got round to.

**Worth keeping:** the 30B produces no inert functions at all, on any board. The
failure the warning addresses is a small-rung phenomenon, which is consistent
with the capability probes and is the more useful thing this exercise found.

---

## 6. Reproducing it

```bash
uv run python - <<'PY'
import glob, math, re
from collections import Counter
from pathlib import Path
from tetris_bench.engine.game import Game
from tetris_bench.sandbox import (UNPLAYABLE, ScoringSandbox,
                                  SandboxValidationError, build_items)

boards = []
for seed in (1, 2, 17):
    for depth in (0, 8, 20):
        game = Game(seed=seed, max_pieces=60)
        for _ in range(depth):
            moves = game.legal_placements()
            if not moves or game.over:
                break
            game.step(moves[len(moves) // 2])
        moves = game.legal_placements()
        if len(moves) >= 2 and not game.over:      # a 1-candidate board is
            boards.append((game.board, moves))     # trivially "constant"
items = [build_items(b, p) for b, p in boards]

tally = Counter()
for path in sorted(glob.glob("runs/published/*/functions/*.py")):
    rung = re.match(r"(qwen3-\d+b)", Path(path).stem).group(1)
    try:
        with ScoringSandbox(Path(path).read_text()) as box:
            per_board = [box.score(it) for it in items]
    except SandboxValidationError:
        continue
    # -inf is the failure sentinel, not a score: exclude it or a crashing
    # function reads as a constant one.
    live = [[s for s in r if s != UNPLAYABLE and s is not None and not math.isnan(s)]
            for r in per_board]
    usable = [l for l in live if len(l) >= 2]
    if not usable:
        continue
    flat = sum(1 for l in usable if len(set(l)) == 1)
    tally[(rung, "constant" if flat == len(usable) else "not")] += 1
for key in sorted(tally):
    print(key, tally[key])
PY
```
