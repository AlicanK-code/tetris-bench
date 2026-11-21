# Published run artifacts

The evidence behind [`docs/findings/`](../../docs/findings/) and the Results
section of the top-level README. Every claim in those documents should be
checkable from here without rerunning a model.

`runs/` is otherwise gitignored, because working output accumulates fast and
most of it is superseded within a day. This directory is the exception: it holds
only the artifacts a document actually cites, copied here deliberately.

## What is in a run

Two file types, written by `loop.py` as a run proceeds:

- **`loop.jsonl`** -- one row per *game*, flattened to a single-level JSON
  object so it loads straight into a dataframe. `split` is `train` (the model
  sees these outcomes as feedback) or `eval` (held out; the curve is read from
  these rows only). `function_sha` identifies which generated function played.
- **`*.py`** -- the scoring function exactly as extracted from the model's
  reply, which is what the sandbox executed.
- **`*.json`** -- the generation that produced it: `prompt`, `reasoning` and
  `raw_reply` verbatim. This is the part that makes a finding auditable rather
  than merely reported: you can read the prompt the model actually got and the
  trace it actually produced.

Everything here is `qwen3` at 4-bit on one MacBook via Ollama, so no file
contains an API key, a URL or any personal data. The `.py` files were written by
a language model and executed only inside the sandbox described in the top-level
README. **Read them, do not import them** -- that is the entire premise of
`sandbox.py`.

## Index

| directory | what it is | cited by |
|-----------|------------|----------|
| `clean-6iter/` | The six-iteration improvement run, one chain, 78 games. The headline curve. | README Results, `docs/timeline.md` |
| `seed-inert/` | Five chains at iteration 0 under model seeds 1-5, 65 games. | [seed-is-inert-at-temperature-zero.md](../../docs/findings/seed-is-inert-at-temperature-zero.md) |
| `noise-floor/` | Repeated iteration-0 generations from one prompt: 5 on the 14B, 2 on the 30B. | [noise-floor-qwen3-14b.md](../../docs/findings/noise-floor-qwen3-14b.md), [noise-floor-qwen3-30b.md](../../docs/findings/noise-floor-qwen3-30b.md) |
| `revise/` | Two independent revisions of the same function from the same feedback. | [first-revision-reweights-not-debugs.md](../../docs/findings/first-revision-reweights-not-debugs.md) |
| `counterexample/` | Revisions given a feature-level counterexample. `1,2,3` are the original trace board; `-p8-1`, `-p24-1` vary it. | [counterexample-fixes-what-feedback-cannot.md](../../docs/findings/counterexample-fixes-what-feedback-cannot.md) |
| `qwen3-4b-iter0/` | The 4B's first functions, including the `strategy_v1` vs `v2` prompt comparison. | [qwen3-4b-iter0-detailed.md](../../docs/findings/qwen3-4b-iter0-detailed.md), [prompt-comparison-and-determinism.md](../../docs/findings/prompt-comparison-and-determinism.md) |

## The two results worth opening a file for

**`clean-6iter/functions/` is a credit-assignment failure you can read.**
Iterations 3, 4 and 5 are the same strategy with the same bug treated three
different ways, and diffing them shows the whole story: `iter3` measures column
height as a row index and subtracts it, `iter4` flips the signs to plus and
scores 25,180 without fixing the definition, and `iter5` corrects the
definition instead -- counting filled cells down from row 0 with a `break`,
which returns 0 on any board with an empty top row and silently zeroes three of
five terms.

```bash
diff runs/published/clean-6iter/functions/qwen3-14b-chain0-iter{3,4}.py
diff runs/published/clean-6iter/functions/qwen3-14b-chain0-iter{4,5}.py
```

**`seed-inert/` is four identical files that cost four generations.** Chains
1-4 share one function sha, `cdaacc8156ca`, because at temperature 0 greedy
decoding never draws from the RNG and the per-chain seed indexes nothing:

```bash
md5 runs/published/seed-inert/functions/*.py          # chains 1-4 collide
```

## Reproducing from these files

A saved function replays in well under a second, with no model involved:

```bash
uv run python analysis/curves.py --log runs/published/clean-6iter/loop.jsonl
uv run python analysis/held_out.py
```

The curve read from `clean-6iter/loop.jsonl` reports iteration 4 at 14,860
rather than the 25,180 quoted in the README. That is not a discrepancy: the run
was played at the old 500-piece budget, which censored iteration 4 on 5 of its
10 held-out seeds. Replaying the saved function at the current default
uncensors it, which is how the 25,180 was obtained and why the default changed.
The rows are kept as they were recorded rather than rewritten, because a log
should say what the run did.
