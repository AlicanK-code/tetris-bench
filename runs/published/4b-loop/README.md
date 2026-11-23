# The 4B loop

5 chains × 6 iterations on `qwen3:4b`, 2 h 22 m, 30 generations. The second rung
ever taken past iteration 0. Cited by
[4b-loop-reweights-a-crash-five-times.md](../../../docs/findings/4b-loop-reweights-a-crash-five-times.md)
and the top-level README.

Seed splits are the CLI defaults, which are exactly what
[`five-chain/`](../five-chain/) and [`ladder/`](../ladder/) used — train
`[1, 2, 17]` fed back, eval `1000-1009` held out — so the curves are directly
comparable to the 14B's.

| file | what it is |
|---|---|
| `loop.jsonl` | 390 rows, one per game. `split` is `train` or `eval`; the curve is read from `eval` only. |
| `functions/*.py` | The 30 scoring functions as extracted from the model's replies. All 30 SHAs are distinct. |
| `functions/*.json` | The generation behind each: `prompt`, `reasoning`, `raw_reply` verbatim. |
| `run.log` | The CLI's own per-iteration output. |

## The file to open

**`functions/qwen3-4b-chain3-iter{1,2,3,4,5}.py`** — five consecutive revisions,
every one of them carrying `total_empty = total_empty(board)`, which shadows the
function it calls and raises `UnboundLocalError` on every scoring call. 342
sandbox failures per game, five times running, while the weights around the
broken line were retuned each time.

The matching `.json` files show the model was told: the revise prompt quotes the
interpreter's error three times, naming the variable.

```bash
grep -n "total_empty = total_empty" functions/*.py
uv run python -c "import json; print(json.load(open(
  'functions/qwen3-4b-chain3-iter5.json'))['prompt'])" | grep UnboundLocal
```
