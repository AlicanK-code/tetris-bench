# Direct mode costs 800x and plays like random

**Date:** 2026-11-23 · **Model:** `qwen3:14b` · **Mode:** `direct`, one call per piece
**Game:** piece seed 1, 20-piece budget, 3 h 44 m wall clock
**Sources:** [`runs/published/direct/`](../../runs/published/direct/) -- the run record, the CLI output and the inference server's per-call timings

This is milestone 7's demonstration, and it is a demonstration rather than an
experiment: one game, one seed, one rung. What it is for is pinning the cost
ratio that justifies `strategy` being the main mode, with a number instead of an
argument.

It produced a second result that was not the goal.

---

## 1. The game

```
0123456789
..........
.###.#....
.#####....
.##.#.####
..#.###...
..#..#....
..#.###...
..#...#...
..#..###..
..##.#....
..#..##...
..####..#.
..###...#.
...##...##
...#....##
...###..##
#...#..##.
#...#..##.
#.######..
#...##.###
```

| | |
|---|---:|
| score | **0** |
| lines cleared | **0** |
| pieces placed | 20 |
| holes | **86** |
| max height | **19** of 20 |
| invalid replies | **0** |
| model calls | 20 |
| tokens in / out | 15,757 / 128,885 |
| wall clock | 13,440.9 s |

Twenty pieces reached row 1. The next piece or two would have ended it.

---

## 2. The cost ratio, which is what this was for

Against the same model in `strategy` mode (56 generations across the published
runs: 7,249 output tokens and 737.6 s per generation, 901.9 pieces played per
generation, 71.9 pieces per game).

The ratio depends on what a generation is amortised over, so both framings:

| per piece | direct | strategy, one game per function | strategy, as actually used |
|---|---:|---:|---:|
| output tokens | **6,444** | 100.8 | 8.04 |
| seconds | **672.0** | 10.25 | 0.818 |
| **ratio** | — | **64x / 66x** | **802x / 822x** |

The conservative framing charges one generation against a single 71.9-piece
game. The second is what the runs do: a function is written once and replayed
across every seed in the split, so its real denominator is 902 pieces.

**At 672 s per piece a full 2,000-piece game is 15.4 days.** That is the whole
reason this mode is a 20-piece demonstration and not a rung on the ladder.

---

## 3. The result that was not the goal

Same seed, same 20-piece budget, the two reference players for comparison:

| agent | score | lines | holes | max height | cost |
|---|---:|---:|---:|---:|---:|
| heuristic (Lee 2013) | **800** | **7** | **1** | **4** | ~0 s |
| **direct, qwen3-14b** | 0 | 0 | **86** | 19 | **3 h 44 m** |
| random (agent seed 0) | 0 | 0 | 76 | 19 | ~0 s |

Three and three-quarter hours of 14B generation bought placements that look like
uniform random choice.

**Stated carefully, because one game cannot support the stronger claim.** Random
play on this seed, over 200 agent seeds, makes 70.6 holes on average (median 70,
range 33-127). The direct agent's 86 sits at about the 80th percentile: worse
than four random games in five, and comfortably inside the distribution. So the
honest reading is **indistinguishable from random, leaning bad** -- not "worse
than random", which a single game cannot establish.

**The zero score is not the evidence.** Random scored 0 on all 200 seeds, so at
a 20-piece budget scoring nothing is what the budget does, not what the agent
did. The informative contrast is the heuristic's 800 points and 1 hole on the
identical sequence: competent play clears 7 lines inside 20 pieces, so the
budget permits scoring and the agent simply did not.

### Formatting was not the failure

**0 invalid replies in 20 calls.** Every answer parsed to a legal index first
time. This is what the agent's design was built to isolate: the reply is an
index into the enumerated legal moves, so every option is legal by construction
and a poor result cannot be explained away as a malformed-output problem. The
14B can say which move it wants. It chooses badly.

For the same model in `strategy` mode the overall rate across all published runs
is **24.53 points per piece**. The failure is specific to picking moves one at a
time, not to the model.

---

## 4. Per-piece latency does not grow with the board

Worth recording because it is the opposite of what a 3-piece smoke run
suggested. That run averaged 520 s per piece against this game's 665.5 s, which
looked like latency rising as the board filled. Over all 20 pieces it does not:

| | |
|---|---:|
| mean | 665.5 s |
| median | 650 s |
| range | 440 - 980 s |
| standard deviation | 178.5 s |
| first 10 pieces | 754.0 s |
| last 10 pieces | **577.0 s** |
| r(piece index, latency) | **-0.279** |

The second half was *faster* than the first and the correlation leans slightly
negative. The prompt is stateless and the choice list stays at 17-34 entries
whatever the board looks like, so there is no mechanism for growth -- the 28%
gap against the smoke run is three samples against twenty, not a trend.

(Latencies here are from the inference server's own log, rounded to 10 s, which
is why they sum to 13,311 s against the client's measured 13,440.9 s. The log is
published as `inference-server-timings.log` so the table is checkable; the
client records only the total.)

**The 20 replies themselves are not published, because `direct` mode does not
save them.** `strategy` mode writes the prompt, reasoning and raw reply for
every generation, which is what makes those findings auditable. The direct agent
keeps only a bounded sample of *invalid* replies, and this game produced none,
so every claim above rests on the aggregate row. A future direct arm should log
the replies.

---

## 5. What this does and does not establish

**Establishes:** the cost ratio, at 64-822x depending on framing, measured
rather than argued; that direct mode cannot be run at the project's normal
2,000-piece budget; and that the 14B's direct-mode play on this sequence is
inside the random distribution while its formatting is perfect.

**Does not establish:** anything about direct mode in general. One game, one
seed, one rung, 20 of 2,000 pieces, one temperature, one prompt version. The
prior work already reports that direct move-picking fails where a scoring
function succeeds, and this is consistent with that, but a single game is
agreement rather than replication.

**Not worth spending more on.** A properly powered direct-mode arm -- several
seeds, several rungs -- is weeks of wall clock for a baseline whose purpose is
to be beaten. The cost figure was the deliverable and it is measured.

---

## 6. Reproducing it

The comparison and the random distribution are free. The game itself is not.

```bash
# The two reference players, identical seed and budget (instant)
uv run tetris-bench play --agent heuristic --seed 1 --max-pieces 20
uv run tetris-bench play --agent random    --seed 1 --max-pieces 20

# Random's hole distribution on this seed, 200 agent seeds (~1 s)
uv run python - <<'PY'
import statistics
from tetris_bench.agents.random_agent import RandomAgent
from tetris_bench.engine.game import Game
from tetris_bench.runner import play_game
h = [play_game(Game(seed=1, max_pieces=20), RandomAgent(seed=s)).final_holes
     for s in range(200)]
print("mean %.1f median %.1f range %d-%d  >=86: %.1f%%"
      % (statistics.fmean(h), statistics.median(h), min(h), max(h),
         100 * sum(x >= 86 for x in h) / len(h)))
PY

# The demonstration itself: 3 h 44 m, needs a local qwen3:14b
uv run tetris-bench direct --model qwen3-14b --seed 1 --max-pieces 20 \
    --log runs/direct/direct.jsonl
```

The strategy-mode reference figures come from the published runs:

```bash
uv run python - <<'PY'
import json, statistics, glob
rows = [json.loads(l) for p in sorted(set(glob.glob("runs/published/**/*.jsonl",
        recursive=True))) for l in open(p)]
g = [r for r in rows if r["model"] == "qwen3-14b" and r["mode"] == "strategy"]
gen = [r for r in g if r.get("model_calls")]
played = [r for r in g if r.get("played")]
pieces = sum(r["pieces_placed"] for r in played)
print("%d generations, %d games, %d pieces -> %.1f pieces per generation"
      % (len(gen), len(played), pieces, pieces / len(gen)))
print("per generation: %.0f out, %.1fs"
      % (statistics.fmean(r["tokens_out"] for r in gen),
         statistics.fmean(r["latency_seconds"] for r in gen)))
print("overall rate %.2f points per piece"
      % (sum(r["score"] for r in played) / pieces))
PY
```
