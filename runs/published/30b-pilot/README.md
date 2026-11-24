# The 30B pilot

6 chains × 6 iterations on `qwen3:30b-a3b`, 3 h 42 m, 36 generations. The third
rung taken past iteration 0, and the first commissioned as a **power pilot**
rather than as an attempt to show improvement: its job was to measure this
rung's paired standard deviation directly, because every power claim in the repo
had been scaling that figure from the 14B. Cited by
[the-30b-ships-the-best-function-and-the-worst-collapse.md](../../../docs/findings/the-30b-ships-the-best-function-and-the-worst-collapse.md)
and the top-level README.

Seed splits are the CLI defaults, the same ones [`five-chain/`](../five-chain/),
[`4b-loop/`](../4b-loop/) and [`ladder/`](../ladder/) used — train `[1, 2, 17]`
fed back, eval `1000-1009` held out — so the curves are directly comparable
across rungs.

| file | what it is |
|---|---|
| `loop.jsonl` | 458 rows, one per game. `split` is `train` or `eval`; the curve is read from `eval` only. |
| `functions/*.py` | The 35 scoring functions as extracted from the model's replies. All 35 SHAs are distinct. |
| `functions/*.json` | The generation behind each: `prompt`, `reasoning`, `raw_reply` verbatim. |
| `run.log` | The CLI's own per-iteration output. |

36 generations produced 35 functions, of which 34 played a game.

## The files to open

**`functions/qwen3-30b-chain1-iter{0,5}.py`** — the project's only clean example
of outcome feedback producing a correct reweighting. The hole penalty rises from
20 to 350 and the line reward falls from 100 to 10. (That was described here as
"the direction the classic Tetris weightings go" until the 8B loop produced
[`8b-loop/functions/qwen3-8b-chain3-iter{0,5}.py`](../8b-loop/functions/), which
moved the same direction and lost 23.11 points per piece. The direction is not
the explanation.) 41.6 → **50.19 points per piece**, above the
hand-written heuristic's 43.5 and the best figure the project has recorded.

**`functions/qwen3-30b-chain2-iter{2,3}.py`** — one character apart. `tops[col]`
is the row index of the topmost filled cell and row 0 is the top, so a *larger*
`sum_tops` means a *lower* stack. Iteration 3 changed `+ sum_tops` to
`- sum_tops`, rewarding tall stacks, and iterations 4 and 5 kept it while
retuning the terms around it. Eval totals fall monotonically: 24,710 → 11,470 →
5,810 → 1,860 → 820.

**`functions/qwen3-30b-chain0-iter5.py`** — the same inversion
(`score_val -= sum_top * 10.0`) inside the project's *second-best* function, at
47.01 points per piece. It does no damage only because a line clear is worth
3,000 and a hole 200 here, so the inverted term never decides a placement that
matters. The bug is not what separates the best chain from the worst.

## The gap in the log

Chain 2 has no iteration 1. That generation emitted exactly 14,000 output tokens
— the configured `max_tokens` — in 701 s and was still writing, so there was no
complete code block to extract. It is logged with `played: false` and no
function file, and it is the first **length-cap** rejection in the project; the
other four rejections were a syntax error and three `import math` violations.

The chain's lineage survived it: `loop.py` keeps the last function that actually
played rather than carrying an empty source forward, so
`chain2-iter2.py` is a revision of `chain2-iter0.py` and shares its first
fourteen lines.
