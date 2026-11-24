# The loop does not repair capability either

**Date:** 2026-11-23 · **Models:** `qwen3:4b`, `qwen3:14b` · no GPU, pure replay
**Sources:** [`runs/published/4b-loop/`](../../runs/published/4b-loop/),
[`runs/published/five-chain/`](../../runs/published/five-chain/),
[`runs/published/clean-6iter/`](../../runs/published/clean-6iter/)

This closes the open question [the ladder write-up](size-ladder-is-a-step.md)
left behind. "Does a small model close on a large one" was ill-posed, since
there is no slope to close, and was restated there as **does the loop move a
rung's probe-clean fraction?** Both completed loops can now answer it, and the
answer is no.

The question mattered because the loop's scores are inside their own noise on
both rungs. If the loop were quietly fixing *broken* functions without moving
*scores*, that would be a real effect the curve cannot see — and it is the one
remaining way the existing findings could be understating what the loop does.
It is not happening.

---

## 1. The fraction does not move

A function is **strategy-capable** when it answers all four probes correctly:
prefers a shallower stack, prefers a clean surface to a buried hole, is not
blind above the first gap, and prefers clearing a row. The bar is deliberately
low — these are not strategy questions — so a failure is a defect, not a
preference.

| loop | it0 | it1 | it2 | it3 | it4 | it5 |
|---|---:|---:|---:|---:|---:|---:|
| **4B**, 5 chains | 1/5 | 1/5 | 1/5 | 1/5 | 1/5 | 1/5 |
| **14B**, 5 chains | 2/5 | 2/5 | 0/5 | 0/5 | 1/5 | 1/5 |
| 14B, 1 chain | 0/1 | 0/1 | 0/1 | 0/1 | 1/1 | 0/1 |
| **30B**, 6 chains | 4/6 | 4/5 | 6/6 | 4/6 | 5/6 | 4/6 |
| **8B**, 10 chains | 3/10 | 2/10 | 3/10 | 4/10 | 5/10 | 5/10 |

Pooled across both five-chain loops, **iteration 0 was 3 of 10 and iteration 5
was 2 of 10.** The fraction went slightly down.

> **Added 2026-11-24: the 30B row above answers the limit this document
> states.** Both original loops ran on rungs where most first attempts are
> broken, so they could only measure *repair*. The 30B starts **4 of 6
> probe-clean** and ends **4 of 6**, with **3 repairs against 3 regressions over
> 28 transitions** — the first rung where refinement was available, and the
> fraction does not move there either. Pooled over all three loops: **4 repairs
> in 68 chances against 5 regressions**, 7 of 16 chains capable at iteration 0
> and 6 of 16 at iteration 5. Among the three 30B chains that were probe-clean
> at both ends, the mean gain was **−10.22** against **+11.30** for the other
> three, which is the wrong sign for a refinement story but not significant
> (exact permutation p = 0.300). See
> [the-30b-ships-the-best-function-and-the-worst-collapse.md](the-30b-ships-the-best-function-and-the-worst-collapse.md).

> **Added 2026-11-24 (later the same day): the 8B row is the best test this
> question will get, and it is still null.** Ten chains on the rung with the
> most broken functions gives **33 repair chances, more than the other three
> rungs combined**, and the probe-clean count does rise across the run -- 3, 2,
> 3, 4, 5, 5 of 10, the largest rise recorded. It does not survive the
> comparison that matters:
>
> | rung | repairs / chances | regressions / chances |
> |---|---|---|
> | `qwen3-4b` | 0 / 20 | 0 / 5 |
> | **`qwen3-8b`** | **5 / 33** | 3 / 17 |
> | `qwen3-14b` | 2 / 24 | 3 / 6 |
> | `qwen3-30b` | 3 / 6 | 3 / 22 |
> | **pooled** | **10 / 83 (12%)** | **9 / 50 (18%)** |
>
> A broken function is repaired 12% of the time it could be; a working one
> breaks 18% of the time it could. Over 133 transitions the sign test on the 19
> discordant pairs gives **p = 1.000**. The 8B also supplies the mechanism this
> document has been describing from the outside: 8 of its 28 live adjacent
> revisions rewrote their weights and then **chose identically on every held-out
> sequence**, one of them provably unable to choose otherwise. Revision that
> cannot change a decision is neither repair nor damage. See
> [the-best-powered-null-and-the-inert-revisions.md](the-best-powered-null-and-the-inert-revisions.md).

### Per chain, the picture is starker

```
4B    chain 0:  C C C C C C        14B   chain 0:  C C x x x x
      chain 1:  x x x x x x              chain 1:  x x x x x x
      chain 2:  x x x x x x              chain 2:  C C x x x x
      chain 3:  x x x x x x              chain 3:  x x x x x x
      chain 4:  x x x x x x              chain 4:  x x x x C C
```

**On the 4B: 0 repairs in 20 chances, and 0 regressions.** The one capable chain
was capable before any feedback existed and stayed that way; the four broken
chains were broken at iteration 0 and all twenty revisions left them broken.
Nothing the loop did changed a single function-level verdict on this rung.

**On the 14B: 1 repair in 20 chances, and 2 regressions.** Pooled: **1 repair in
40 chances against 2 regressions.** The three transitions in the whole corpus:

| | transition | before | after |
|---|---|---|---|
| 14B chain 0 | it1 → it2 | clean | **height broken** |
| 14B chain 2 | it1 → it2 | clean | **holes broken** |
| 14B chain 4 | it3 → it4 | height + above-gap broken | **clean** |

Two of the three are revisions *destroying* a capability the function already
had. The single genuine repair is 14B chain 4 at iteration 4, which then held.

---

## 2. Terms churn; functions do not become whole

The loop is not inert at the level of individual terms. It moves them around,
roughly symmetrically, and never enough to finish the job.

| probe | 4B repaired | 4B broken | 14B repaired | 14B broken |
|---|---:|---:|---:|---:|
| height | 2 | 3 | — | — |
| holes | 1 | 1 | — | — |
| above-gap | 2 | 2 | — | — |
| lines | 1 | 1 | — | — |
| **total** | **6** | **7** | **4** | **2** |

The 4B's six term-level repairs produced **zero** function-level repairs, because
a function with two broken terms that fixes one is still broken. 4B chain 2 is
the clearest case: its height term went from inverted to correct at iteration 2
and stayed correct, while its holes term stayed blind for all six iterations, so
the function never became capable and its score stayed flat around 7-8 before
collapsing to 0.

That is the mechanism behind the headline. **Revision operates on terms, and
capability is a conjunction over terms.** Fixing them one at a time, with a
roughly equal chance of breaking another, is a random walk that does not reach
"all four correct".

---

## 3. On the 4B, capability does not predict score

Worth stating because it bounds what this finding implies.

| | median points per piece | n |
|---|---:|---:|
| probe-clean | 4.66 | 6 |
| probe-broken | 4.16 | 24 |

Essentially no separation, and **the best score in the entire 4B run — 13.05
points per piece, chain 1 at iteration 5 — is probe-broken**, inverted on height
at every one of its six iterations. This is consistent with
[the ladder's finding](size-ladder-is-a-step.md) that the probes only predict a
score from the 8B up.

So on this rung "the loop did not repair capability" and "the loop did not
improve scores" are two separate null results that happen to agree, rather than
one result seen twice.

---

## 4. What this closes, and what it does not

**Closes:** the restated ladder question. The loop does not move the
probe-clean fraction on either rung that has been run through it. The
hypothesis that the loop is doing invisible repair work the score cannot see is
refuted on the available data.

**Does not close:** anything about rungs with more capability to begin with. Both
loops are rungs where most first attempts are already broken (4B 4/15 on the
ladder, 14B 3/15). A rung that starts mostly capable would be measuring
something different — refinement rather than repair — and the 30B is that rung
at 11/15. **A 30B loop is now the only way to test repair-versus-refinement**,
which is a second reason to want one beyond the paired-noise pilot.

**Tested since:** the *rate of zeros and crashes* was the remaining candidate,
and it is null as well — 5 revivals against 5 deaths across 50 transitions,
p = 1.000, and a required sample size of 15-55 chains against the 5 that ran.
All three ways the loop could have been doing something the curve cannot see
have now been checked. See
[the-zeros-rate-does-not-move-either.md](the-zeros-rate-does-not-move-either.md).

---

## 5. Reproducing it

No model, no GPU, a few seconds.

```bash
uv run python analysis/term_diagnostics.py runs/published/4b-loop/functions
uv run python analysis/term_diagnostics.py runs/published/five-chain/functions
```

The second prints **33** functions, not 30: `five-chain/functions/` also holds
three `qwen3-4b-seed1-*` files from the earlier prompt-comparison arm. Every
figure in this document is computed over the 30 whose names carry a chain and an
iteration, which is what the snippet below filters for.

The trajectory and the transition counts:

```bash
uv run python - <<'PY'
import re
from tetris_bench.term_diagnostics import classify_directory

for d, name in (("runs/published/4b-loop/functions", "4B"),
                ("runs/published/five-chain/functions", "14B")):
    res = {}
    for v in classify_directory(d):
        m = re.search(r"chain(\d+)-iter(\d+)", v.label)
        if m:   # five-chain/functions also holds three strays from an earlier arm
            res[(int(m.group(1)), int(m.group(2)))] = v
    print("\n%s clean by iteration:" % name,
          " ".join("%d/5" % sum(res[(c, i)].strategy_capable for c in range(5))
                   for i in range(6)))
    rep = bro = opp = 0
    for c in range(5):
        for i in range(5):
            a, b = res[(c, i)].strategy_capable, res[(c, i + 1)].strategy_capable
            opp += not a
            rep += (not a) and b
            bro += a and (not b)
    print("  %d repairs / %d chances, %d regressions" % (rep, opp, bro))
PY
```
