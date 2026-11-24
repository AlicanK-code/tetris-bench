# The 8B loop

10 chains × 6 iterations on `qwen3:8b`, 7 h 08 m, 60 generations. The fourth and
last rung of the ladder taken through the improvement loop, and the largest run
in the project: ten chains were affordable here (427 s a generation) where they
are not on the 14B or the 30B, so this is the one curve powered well enough for
its null to carry a number. Cited by
[the-best-powered-null-and-the-inert-revisions.md](../../../docs/findings/the-best-powered-null-and-the-inert-revisions.md)
and the top-level README.

Seed splits are the CLI defaults, the same ones [`five-chain/`](../five-chain/),
[`4b-loop/`](../4b-loop/), [`30b-pilot/`](../30b-pilot/) and
[`ladder/`](../ladder/) used — train `[1, 2, 17]` fed back, eval `1000-1009`
held out — so the curves are directly comparable across rungs.

| file | what it is |
|---|---|
| `loop.jsonl` | 730 rows, one per game. `split` is `train` or `eval`; the curve is read from `eval` only. |
| `functions/*.py` | All 60 scoring functions as extracted from the replies. Every SHA is distinct. |
| `functions/*.json` | The generation behind each: `prompt`, `reasoning`, `raw_reply` verbatim. |
| `run.log` | The CLI's own per-iteration output, including the wait-for-GPU handoff from the 30B pilot. |

60 generations produced 60 functions, of which **55 played**: five were rejected
by the AST validator, all five for `import math`.

## The files to open

**`functions/qwen3-8b-chain1-iter{4,5}.py`** — a revision that cannot change
anything. Every weight is doubled (`100, 50, 10, 10` → `200, 100, 20, 20`) and
one always-irrelevant term is dropped. Scaling a linear score uniformly cannot
move its argmax, and the two functions score **identically on all thirteen
sequences**, game for game, piece for piece. 428 seconds for a provable no-op.

**`functions/qwen3-8b-chain3-iter{0,5}.py`** — the run's best opening function
collapsing. `lines * 100 - holes * 1` becomes `lines * 50 - holes * 100 -
max_h * 150 - unevenness * 150`: a line is now worth half a hole and a third of
the height it costs. 34.57 → **11.46** points per piece. The same qualitative
move — hole penalty up, line reward down — that the 30B's chain 1 made on its
way to the project's best function, which is why that pilot's "it found the
right direction" gloss no longer stands.

**`functions/qwen3-8b-chain5-iter{0,1,2,3,4,5}.py`** — the import rule in one
chain. It imports `math` at iterations 0, 2 and 4, is told each time in the
validator's own words, and complies at 1 and 5. Half the chain's budget —
20,691 output tokens, 1,325 seconds — produced nothing. It is also the run's
only monotone-rising chain: 17.75 → 27.10 → 37.81, every step written with no
game feedback at all.

**`functions/qwen3-8b-chain{0,1}-iter0.py`** — byte-identical to
[`ladder/functions/qwen3-8b-chain{0,1}-iter0.py`](../ladder/functions/), from the size
ladder, run the day before. Chains 2–9 are not. Two of ten generations reproduced
under the same prompt and the same per-chain seed at temperature 0.7.

## The gap in the curve

Five positions logged no held-out game: chains `(1,1)`, `(2,2)`, `(5,0)`,
`(5,2)` and `(5,4)`. All five are rejections — `played` is `false` and
`invalid_outputs` is 1 — not gaps in the log. The analysis excludes them rather
than entering them as zeros, which is what `analysis/curves.py` does by default;
pass `--log` to this file to see the other convention, where a rejection counts
as a measured zero and the medians read 8.3 → 17.0 instead of 15.63 → 17.04.
