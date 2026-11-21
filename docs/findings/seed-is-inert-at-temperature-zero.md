# Finding: the per-chain seed buys nothing at temperature 0 — chains were clones

**Date:** 2026-11-21 · **Model:** `qwen3:14b`
**Scripts:** `analysis/seed_probe.py`, `analysis/repeat_probe.py`
**Run:** `runs/loop.jsonl` — 5 chains × 1 iteration, the intended
iteration-0 variance measurement
**Artifacts:** `runs/functions/qwen3-14b-chain{0,1,2,3,4}-iter0.py`

The measurement this run was built to make did not happen, and the reason is
mechanical. It is recorded because the same mistake is easy to make again, and
because the fix changes a design decision stated in `CLAUDE.md`.

---

## 1. What the run produced

Five chains, generating under model seeds 1–5 (commit `17730da`):

| chain | seed | function sha | tokens out | held-out mean |
|-------|------|--------------|------------|---------------|
| 0 | 1 | `5d31b3f92254` | 8,711 | 20 |
| 1 | 2 | `cdaacc8156ca` | 8,914 | 0 |
| 2 | 3 | `cdaacc8156ca` | 8,914 | 0 |
| 3 | 4 | `cdaacc8156ca` | 8,914 | 0 |
| 4 | 5 | `cdaacc8156ca` | 8,914 | 0 |

Chains 1–4 are **byte-identical**: same sha, same token count, same thirteen
game outcomes down to `mean_spread` at four decimals. Four of the five samples
are one sample counted four times.

`curves.py` reports `generation noise, between chains: 9` for this run. That
number is an artefact of the collision and must not be quoted: it is the spread
of {20, 0, 0, 0, 0}, which is four copies of one draw.

## 2. Why: greedy decoding never consults the RNG

At temperature 0 the sampler takes the argmax at every step. There is no draw,
so there is no random number for a seed to index. The seed is not ignored by
Ollama — it is *unreachable*.

`analysis/seed_probe.py`, three seeds at each of two temperatures, hashing the
whole message (this is a thinking model, so a short generation's tokens go to
`reasoning`, and `content` comes back empty):

```
--- temperature 0.0 ---
  seed 1: e586dcc89558
  seed 2: e586dcc89558     one sha: the seed is inert
  seed 3: e586dcc89558
--- temperature 1.0 ---
  seed 1: d68f6d5338e9
  seed 2: 83447e0e04cc     three shas: the seed is live
  seed 3: b4127c61f073
```

So `chains` and `temperature: 0.0` are mutually contradictory as configured.
`CLAUDE.md` asks for independent chains *because* "several samples per iteration
are needed before a difference means anything"; at temperature 0 the loop can
only ever draw one sample and pay N times for it.

## 3. The correction this overturns

`clients/client.py` carried, in the docstring of `complete`:

> at temperature 0 the seed is the *only* thing that distinguishes two requests
> for the same prompt

Refuted. At temperature 0 the seed distinguishes **nothing**. The sentence was
written when the per-chain seed was added and was never tested against the
model; this run tested it.

The older note in `clients/config.py` — that the seed is honoured at temperature
1.0, where a fixed seed gives bit-identical output — **stands**, and §4 confirms
it independently. The two claims are about different things: whether a *fixed*
seed repeats (it does) versus whether *different* seeds diverge (they do not, at
temperature 0).

## 4. Raising temperature does not cost reproducibility

The obvious objection to sampling is that it trades away the determinism the
benchmark is built on. It does not. `analysis/repeat_probe.py`, one seed, three
consecutive calls:

```
temp 1.0, seed 7: ['37b2637fdffe', '37b2637fdffe', '37b2637fdffe']  -> reproducible
temp 0.7, seed 7: ['31b8f9e9ad7b', '31b8f9e9ad7b', '31b8f9e9ad7b']  -> reproducible
```

Reproducibility moves from `prompt -> output` to `(prompt, seed) -> output`,
which is the stronger guarantee of the two, and the one this project needs:
chain *k* stays exactly replayable from `(prompt, seed + k)` while differing
from its siblings.

It is also worth being clear that `prompt -> output` was **already** unavailable
on this rung. Two runs of a byte-identical prompt at temperature 0 with seed 1
produced different functions — floating-point non-associativity in parallel GPU
reductions, which no seed removes
([prompt-comparison-and-determinism.md](prompt-comparison-and-determinism.md)).
Temperature 0 was buying a determinism the hardware did not deliver.

**Caveat, stated because it limits §4.** These probes are 120-token
generations. Floating-point divergence accumulates with length, so a fixed seed
repeating over 120 tokens is not evidence that it repeats over the ~9,000 a real
strategy generation takes. Per-chain reproducibility at generation length is
untested, and the honest claim is narrower than the probe looks: the seed is
*honoured*, not that a long chain is replayable.

## 5. Incidental: both iteration-0 functions had the inverted-height bug

Not what the run was for, but it is two more samples of a pattern now seen
repeatedly on this rung. Both distinct functions measured column height as a
**row index** on a board whose row 0 is the top:

- `5d31b3f92254` sets `h = row` of the topmost filled cell, so a *smaller*
  number means a *taller* column, then subtracts `aggregate_height` — rewarding
  tall stacks. Its `holes` term, `sum(h for h in heights if h < 20)`, sums
  heights and counts no holes at all.
- `cdaacc8156ca` counts filled cells downward from row 0 with a `break`, which
  returns 0 for every column on any board whose top row is empty. Two of its
  four terms are identically zero. Its hole count tests `any(filled_row > row)`
  — an empty cell with something *below* it, which is free space, not a hole.

Both block out at 14–33 pieces on every seed. This is the same family of bug as
iterations 3 and 5 of the clean six-iteration run (`docs/timeline.md`), and it
is the single most common failure on this rung: the model writes a plausible
heuristic against the wrong row convention and the sign of its main term ends up
backwards.
