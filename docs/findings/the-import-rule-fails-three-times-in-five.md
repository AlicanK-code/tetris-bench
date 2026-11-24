# The import rule fails three times in five

**Date:** 2026-11-23 · **Models:** all four rungs · no GPU, corpus audit
**Sources:** [`runs/published/`](../../runs/published/) — 131 generations
**Prompt:** `strategy_v3`, SHA `f3a0cb0af765`, byte-identical across the ladder

The ladder write-up recorded that three of the project's four rejections were
`import math` "against a prompt that forbids imports in bold", and left
quantifying it open. Quantified here, and **the denominator is the finding.**

---

## 1. The four rejections

> **Added 2026-11-24: there are now five, and the fifth is a different
> phenomenon.** The 30B pilot's chain 2 produced no function at iteration 1
> because the generation emitted exactly **14,000 output tokens — the configured
> `max_tokens`** — in 701 s and was still writing, so there was no complete code
> block to extract. That is a **length cap at a revision step**, not a rule
> violation at iteration 0. It does not change any denominator below, which
> counts generations that reached for `math`, but it does mean "rejection" in
> this project names two unrelated events: a function the validator refused and
> a reply that never finished. See
> [the-30b-ships-the-best-function-and-the-worst-collapse.md](the-30b-ships-the-best-function-and-the-worst-collapse.md).

Every rejection in the published corpus, all at iteration 0:

| run | rung | chain | reason |
|---|---|---:|---|
| ladder | `qwen3-8b` | 4 | syntax error on line 12: invalid syntax |
| ladder | `qwen3-8b` | 7 | **`import math`** |
| ladder | `qwen3-14b` | 9 | **`import math`** |
| ladder | `qwen3-14b` | 14 | **`import math`** |

The validator's own message, for the three:

```
line 1: imports are not allowed (found math);
        'math' is already available without importing it
```

Cost: **3 generations, 27,743 output tokens, 38.6 minutes** of the ladder's wall
clock, producing nothing.

---

## 2. The prompt said so, in bold, with the answer in it

This is not a case of a model needing something the prompt withheld. The
instruction as actually sent, verified against the generation record rather than
the template file:

> - **No imports.** `math` is already available as a name - use `math.sqrt(...)`
>   directly, with no import statement.

It is bolded, it names the substitute, and **it gives the worked example**. All
three rejected functions use exactly one `math` call: `math.sqrt`. The call in
the example.

---

## 3. The denominator that matters

Quoted as "3 of 60 ladder generations", this is a 5% nuisance. That is the wrong
denominator, because 55 of those 60 had no occasion to obey the rule at all —
they never wanted `math`.

**Five functions in the entire 131-generation corpus reach for `math`. All five
want `math.sqrt`. Three of the five added the forbidden import.**

| function | outcome |
|---|---|
| `ladder/qwen3-4b-chain1-iter0` | used `math.sqrt` correctly, no import |
| `ladder/qwen3-8b-chain5-iter0` | used `math.sqrt` correctly, no import |
| `ladder/qwen3-8b-chain7-iter0` | **imported — rejected** |
| `ladder/qwen3-14b-chain9-iter0` | **imported — rejected** |
| `ladder/qwen3-14b-chain14-iter0` | **imported — rejected** |

**Among generations with occasion to follow the instruction, the failure rate is
60%.** And the two successes matter as much as the three failures: they
demonstrate the instruction is followable and the sandbox's pre-injected `math`
works as advertised, so the failures cannot be explained by the facility being
broken or the wording being impossible.

By rung, with the caveat that these are single-digit counts: 4B 0 of 1, 8B 1 of
2, 14B 2 of 2, 30B 0 of 0 — the top rung never reached for `math` at all, so it
has no score on this instruction rather than a perfect one.

---

## 4. Revisions never do it, under identical wording

| condition | generations | import rejections |
|---|---:|---:|
| iteration 0 | 76 | **3** |
| revisions | 55 | **0** |

> **Correction (2026-11-23, same day).** This section first attributed the
> contrast to the revise prompt stating the rule *worse* — an unbolded
> parenthetical with no example — quoting `revise_v1.md`. That is wrong.
> **`revise_v1` was never used in any published run.** The loop uses one
> template for every iteration (`loop.py`: `TEMPLATE = "strategy_v3"`), and its
> own comment says why: earlier versions used `strategy_v2` at iteration 0 and
> `revise_v1` afterwards, "which differed in several ways at once", so the
> prompt change was tangled up with the measured effect. All 134 published
> generations carry the strategy body; a revision is that same text plus a
> feedback block and the previous function.

So the wording is **identical** in both conditions — bolded, with the
`math.sqrt` example — and the contrast cannot be a wording effect at all. What
differs is only the feedback block and the inclusion of the model's previous
function, which is already import-free and therefore **a template to copy where
iteration 0 has nothing but prose.**

That is now the only explanation standing rather than one of two, which makes it
stronger evidence and still not proof: the two conditions differ in those two
ways together, and nothing here separates "copies the previous function's shape"
from "behaves differently once it has any example of a valid answer".

---

## 5. What this is, and what it is not

**Is:** an instruction-following measurement. A bolded rule, carrying its own
substitute and a worked example, is ignored by 3 of the 5 generations that have
occasion to apply it. That is a capability result about the rungs, not an
artefact of the harness — which is what the ladder write-up suspected and could
not yet say.

**Is not:** a reason to change the sandbox. Rejecting the import is correct; the
AST allowlist exists so a violation fails instantly with a readable reason
instead of burning a timeout, and it did exactly that in all three cases. The
cost of a rejection is one wasted generation, which is the intended price.

**Open, and cheap only in principle:** whether a rung can follow the instruction
when it is restated. Changing the prompt breaks byte-identical comparability
with these 60 generations, so it needs its own arm rather than a patch — and at
5 occasions in 131 generations, an arm powered to measure a change in a 60% rate
would need to be very large or to prompt specifically for a function that wants
a square root. The second option is probably the honest design.

---

## 6. Reproducing it

```bash
# Every rejection, with its reason
uv run python - <<'PY'
import glob, json
from pathlib import Path
from tetris_bench.sandbox import SandboxValidationError, validate_source

seen = set()
for path in sorted(set(glob.glob("runs/published/*/loop.jsonl"))):
    for line in open(path):
        row = json.loads(line)
        key = (path, row["model"], row["chain"], row["iteration"])
        if key in seen or row.get("played"):
            continue
        seen.add(key)
        name = "%s-chain%d-iter%d" % (row["model"], row["chain"], row["iteration"])
        src = Path(path).parent / "functions" / (name + ".py")
        try:
            validate_source(src.read_text())
            print("%-30s accepted?" % name)
        except SandboxValidationError as exc:
            print("%-30s %s" % (name, exc))
PY

# Everyone who reached for math, and whether they imported it
grep -l "math\." runs/published/*/functions/*.py | while read f; do
  grep -q "^import math" "$f" && echo "IMPORTED  $f" || echo "correct   $f"
done
```
