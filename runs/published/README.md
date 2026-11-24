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
contains an API key, a credential or any personal data. The only URL anywhere in
these artifacts is one a model cited inside its own reasoning trace
(`five-chain/functions/qwen3-14b-chain2-iter5.json`), which is model output and
not necessarily a real reference. The `.py` files were written by
a language model and executed only inside the sandbox described in the top-level
README. **Read them, do not import them** -- that is the entire premise of
`sandbox.py`.

## Index

| directory | what it is | cited by |
|-----------|------------|----------|
| `ladder/` | All four rungs at iteration 0, 15 chains each: 60 generations, 728 games, one byte-identical prompt. | [size-ladder-is-a-step.md](../../docs/findings/size-ladder-is-a-step.md), README Results |
| `five-chain/` | The 14B over six iterations on five independent chains, 390 games. Supersedes `clean-6iter/` as the improvement result. | README Results |
| `clean-6iter/` | The six-iteration improvement run, one chain, 78 games. Single-chain predecessor of `five-chain/`; still the source of the credit-assignment example. | README Results, `docs/timeline.md` |
| `4b-loop/` | The 4B over six iterations on five independent chains, 390 games. The second rung taken past iteration 0, and the source of the five-revisions-of-a-crash result. | [4b-loop-reweights-a-crash-five-times.md](../../docs/findings/4b-loop-reweights-a-crash-five-times.md), README Results |
| `30b-pilot/` | The 30B over six iterations on six independent chains, 458 games. The power pilot: commissioned to measure this rung's paired σ_d rather than to show improvement. Holds the best function in the project and its worst collapse. | [the-30b-ships-the-best-function-and-the-worst-collapse.md](../../docs/findings/the-30b-ships-the-best-function-and-the-worst-collapse.md), README Results |
| `8b-loop/` | The 8B over six iterations on **ten** independent chains, 730 games — the largest run here, and the fourth and last rung taken past iteration 0. Holds the provable no-op revision and five `import math` rejections. | [the-best-powered-null-and-the-inert-revisions.md](../../docs/findings/the-best-powered-null-and-the-inert-revisions.md), README Results |
| `seed-inert/` | Five chains at iteration 0 under model seeds 1-5, 65 games. | [seed-is-inert-at-temperature-zero.md](../../docs/findings/seed-is-inert-at-temperature-zero.md) |
| `noise-floor/` | Repeated iteration-0 generations from one prompt: 5 on the 14B, 2 on the 30B. | [noise-floor-qwen3-14b.md](../../docs/findings/noise-floor-qwen3-14b.md), [noise-floor-qwen3-30b.md](../../docs/findings/noise-floor-qwen3-30b.md) |
| `revise/` | Two independent revisions of the same function from the same feedback. | [first-revision-reweights-not-debugs.md](../../docs/findings/first-revision-reweights-not-debugs.md) |
| `counterexample/` | Revisions given a feature-level counterexample. `1,2,3` are the original trace board; `-p8-1`, `-p24-1` vary it. | [counterexample-fixes-what-feedback-cannot.md](../../docs/findings/counterexample-fixes-what-feedback-cannot.md) |
| `direct/` | The milestone 7 direct-mode demonstration: one 20-piece game, one model call per piece, 3 h 44 m. The only `mode: "direct"` row in the repo. | [direct-mode-costs-800x-and-plays-like-random.md](../../docs/findings/direct-mode-costs-800x-and-plays-like-random.md), README Results |
| `qwen3-4b-iter0/` | The 4B's first functions, including the `strategy_v1` vs `v2` prompt comparison. | [qwen3-4b-iter0-detailed.md](../../docs/findings/qwen3-4b-iter0-detailed.md), [prompt-comparison-and-determinism.md](../../docs/findings/prompt-comparison-and-determinism.md) |
| `reweighting/` | 23 reconstructed variants, not model output: each is one of two saved functions with exactly one thing changed, for the term-level replay. | [the-best-revision-was-a-repair.md](../../docs/findings/the-best-revision-was-a-repair.md), README Results |
| `figures/` | The pictures the top-level README shows, beside the logs they are drawn from. Regenerate with `analysis/plots.py` and `analysis/power_figure.py`. | README, [its own README](figures/README.md) |

## The results worth opening a file for

**`ladder/functions/qwen3-30b-chain3-iter0.py` is the best function the project
has produced, and it was the first thing that chain wrote.** 22 lines: lines,
holes and bumpiness, no height term at all. It reaches 96% of the hand-written
heuristic on held-out seeds with no feedback of any kind. Its sibling
`qwen3-30b-chain11-iter0.py` from the same prompt and the same rung scores zero,
which is the spread this benchmark has to measure through.

Four files in `ladder/functions/` were refused before they ever ran, and the
`.json` beside each shows the model producing them:

```bash
grep -l "^import math" runs/published/ladder/functions/*.py    # three of the four
```

Those three imported `math` against a prompt that forbids imports in bold, which
makes them instruction-following failures rather than harness artefacts. The
fourth, `qwen3-8b-chain4-iter0.py`, is a plain syntax error.

**`8b-loop/functions/qwen3-8b-chain1-iter{4,5}.py` is a revision that cannot
change anything.** Every weight is doubled and one always-irrelevant term
dropped; scaling a linear score uniformly cannot move its argmax, and the two
functions score identically on all thirteen sequences, game for game.

```bash
diff runs/published/8b-loop/functions/qwen3-8b-chain1-iter{4,5}.py
```

**`8b-loop/functions/qwen3-8b-chain5-*` is the import rule in one chain.** It
imports `math` at iterations 0, 2 and 4, is told each time in the validator's
own words, and complies at 1 and 5 — half its budget producing nothing:

```bash
grep -ln "import math" runs/published/8b-loop/functions/*.py   # all five rejections
```

Four of the five put the import at column 0; `chain1-iter1` puts it on line 16,
*inside* the function body, which the AST allowlist rejects just the same.

## Two more worth opening a file for

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
