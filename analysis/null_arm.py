"""The zero point on the feedback axis: revise with no outcome data at all.

Two arms have been run against the 14B's broken iteration-0 function, and both
of them carried the full outcome summary:

- **control** (outcome feedback): two revisions kept the broken hole count
  `heights[col] > row` character-for-character and changed only the weights.
  Held-out 130 and 85 against iteration 0's 110 -- flat
  (docs/findings/first-revision-reweights-not-debugs.md).
- **counterexample** (outcome feedback *plus* one board's true heights and true
  hole count): held-out 2,540, hole count fixed, replicated across two distinct
  generations (docs/findings/counterexample-fixes-what-feedback-cannot.md).

So the recorded comparison is feedback against feedback-plus-trace, and there is
no zero point. Nothing in it rules out the dullest explanation available: that a
second look at its own code is what helped, and the content of the feedback was
irrelevant either way. If a prompt carrying **no** outcome data also fixes the
bug, the 23x means something far smaller than it appears to.

This arm supplies that zero point. The prompt is the control's, with the outcome
block removed and nothing put in its place: the previous function and the
instruction to improve it, and no score, lines, pieces, holes, height,
bumpiness, cause of death, board snapshot or mechanical note.

**Why more than one generation.** Varying only *which* board the counterexample
showed gave held-out 2,540 (piece 16), 120 (piece 24) and 5 (piece 8) -- the last
a function that replaced the broken hole count with a worse one. Three nominally
equivalent prompts, a 500-fold spread in outcome. Against that, a single null
sample would establish nothing, so `--runs` defaults to 3 and the per-run output
reports generation length so the samples can be compared to each other.

All five of those generations predate the fix to `counterexample_arm`'s prompt
builder, which had been dropping the measurement declaration the control carries.
They are internally comparable -- same builder throughout -- but they are *not*
comparable to anything built today, and the contrast this arm owns is
**null against control**, which is a clean one-block difference. Null against
counterexample is not a contrast to draw from the recorded numbers.

**Why the correctness check is a measurement rather than a string test.** The
counterexample arm reports `"heights[col] > row" not in source`, which said
"changed: True" for the piece-8 function that is *more* wrong than the original.
A string test cannot tell a fix from a different bug. This script instead
rewrites the generated function so it returns its own hole tally, runs that in
the sandbox on boards whose true hole count the engine knows, and prints both
numbers. That is pure CPU and needs no model.

**The asymmetry, stated up front.** Removing the outcome block removes about 700
characters, so the null prompt is ~14% shorter than the control's 5,157. It
cannot be closed without adding content, and any content added would be its own
treatment, so the script measures the gap and prints it rather than papering over
it. `--variant withheld` offers the alternative: keep the control's headings and
bullet labels with every value replaced by `(not reported)`, which holds the
prompt's shape and the "for scale, ~21,600" anchor fixed at the cost of telling
the model outright that measurements exist and are being withheld. Run both if
the bare arm comes out positive; see the README note in `main`'s output.

    uv run python analysis/null_arm.py --model qwen3-14b
    uv run python analysis/null_arm.py --variant withheld --runs 1 --start-index 4
    uv run python analysis/null_arm.py --runs 0     # prompts and probe only, no model

`--runs 0` is the dry run: it prints the prompt lengths and probes the function
being revised without making a single model call, which takes about a second and
is how everything here was verified while a GPU was busy elsewhere.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import time
from dataclasses import dataclass, replace
from pathlib import Path

# Both arms live in analysis/, which Python puts on the path when it runs this
# file. Importing rather than copying is deliberate: the headline number here is
# a *comparison* of three prompts, so the counterexample prompt has to be the one
# that arm really builds, and the held-out measurement has to be the same
# instrument rather than a second copy of it that can drift.
from counterexample_arm import (
    HELD_OUT_SEEDS,
    build_counterexample_prompt,
    held_out,
    sample_boards,
)

from tetris_bench.agents.strategy import MEASUREMENT_DECLARATION, extract_code
from tetris_bench.clients.client import ModelClient
from tetris_bench.clients.config import load_model_config
from tetris_bench.engine.board import Board
from tetris_bench.loop import (
    LoopConfig,
    Outcome,
    build_prompt,
    play_function,
)
from tetris_bench.metrics import holes
from tetris_bench.prompts import render
from tetris_bench.sandbox import FUNCTION_NAME, UNPLAYABLE, ScoringSandbox

#: The board the counterexample arm's three recorded runs used. Fixed here
#: because the point of printing that prompt's length is to compare against the
#: run that produced 2,540, not against some other configuration of that arm.
COMPARISON_PIECE = 16

#: The local variable whose value the hole probe reads back. Every function this
#: experiment has produced keeps its hole tally in a variable with this name; one
#: that does not simply reports the probe as unavailable.
TALLY_VARIABLE = "holes"

#: Stands in for each withheld number in the `withheld` variant. "(not reported)"
#: rather than "(withheld)" or "(not measured)": the games were played and the
#: numbers do exist, so only "not reported" is true.
NOT_REPORTED = "(not reported)"

#: A placement for the hole probe to be called with. The probe returns the hole
#: tally, which is computed from the board alone, so these values cannot affect
#: the answer -- the keys are here only so that a function which reads
#: `placement["lines_cleared"]` on its way to the return does not raise.
PROBE_PLACEMENT = {
    "kind": "O",
    "rotation": 0,
    "column": 0,
    "row": 0,
    "cells": [[0, 0], [0, 1], [1, 0], [1, 1]],
    "lines_cleared": 0,
}


def bare_feedback_section(previous: Outcome) -> str:
    """The control's feedback section with the outcome block cut out.

    Compare :func:`tetris_bench.loop.build_prompt`: this is that string verbatim,
    minus the `## How your last attempt went` heading and the summary under it.
    Everything the model still sees -- the heading for its own code, the code, and
    the closing instruction -- is character-identical to the control, so the only
    difference is the presence of outcome data.

    Note what goes with it. The "for scale, a good scoring function reaches
    around 21,600" anchor lives *inside* the outcome block, so a bare strip
    removes that too. It is not outcome data about this function, so its removal
    is a second, smaller difference from the control rather than part of the
    manipulation. The `withheld` variant keeps it.
    """
    return (
        "## The function you wrote\n\n"
        f"```python\n{previous.source}```\n\n"
        "Write an improved version below. You may keep whatever worked, "
        "change whatever did not, and restructure freely.\n"
    )


def withheld_feedback_section(previous: Outcome, config: LoopConfig) -> str:
    """The control's feedback section with its shape kept and its numbers gone.

    Mirrors the headings and bullet labels of
    :meth:`tetris_bench.feedback.Feedback.render` -- if that changes, this goes
    out of date and the lengths printed by :func:`main` will show it.

    This is the more conservative isolation on prompt *shape*: same headings,
    same labels, same scale anchor, so the character difference from the control
    is small. It buys that by adding a treatment of its own -- the model is told
    in so many words that measurements exist and are not being shown -- which a
    bare strip does not do. Which of the two confounds is worse is a judgement;
    both are offered so the pair can be run.
    """
    scale = (
        f"\n- for scale, a good scoring function reaches around "
        f"{config.reference_score} on this piece sequence"
        if config.reference_score is not None
        else ""
    )
    return (
        "## How your last attempt went\n\n"
        "## How your function played\n\n"
        "Your function was played, but none of the measurements are reported "
        "this time.\n\n"
        f"- score: {NOT_REPORTED}\n"
        f"- lines cleared: {NOT_REPORTED}\n"
        f"- pieces placed: {NOT_REPORTED}\n"
        f"- how it ended: {NOT_REPORTED}"
        f"{scale}\n\n"
        "## The state of the board\n\n"
        f"- holes at the end: {NOT_REPORTED}\n"
        f"- tallest column at the end: {NOT_REPORTED}\n"
        f"- surface unevenness at the end: {NOT_REPORTED}\n\n"
        f"the final position: {NOT_REPORTED}\n\n"
        "## The function you wrote\n\n"
        f"```python\n{previous.source}```\n\n"
        "Write an improved version below. You may keep whatever worked, "
        "change whatever did not, and restructure freely.\n"
    )


def build_null_prompt(config: LoopConfig, previous: Outcome, variant: str) -> str:
    """The control's prompt with the outcome data removed. Everything else identical.

    The measurement declaration stays, because the control has it
    (:data:`tetris_bench.loop.MEASUREMENT_DECLARATION`, on by default). It names
    the quantities without giving any values, which is exactly the axis this arm
    wants held fixed: the model keeps the vocabulary and loses the numbers.

    One inconsistency is inherent to the manipulation and worth knowing about:
    that declaration promises the model it *will* be told the score, the holes
    and the rest, while the prompt then says nothing about its last attempt. The
    alternative -- dropping the declaration -- would change a second block
    relative to the control, which is worse.
    """
    section = (
        bare_feedback_section(previous)
        if variant == "bare"
        else withheld_feedback_section(previous, config)
    )
    return render(
        config.template,
        width=10,
        height=20,
        last_row=19,
        per_call_seconds=config.per_call_seconds,
        measurement_section=MEASUREMENT_DECLARATION if config.declare_metrics else "",
        feedback_section=section,
    )


def _assigns(definition: ast.FunctionDef, variable: str) -> bool:
    """Whether the function ever assigns to a plain variable of this name."""
    for node in ast.walk(definition):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AugAssign | ast.AnnAssign):
            targets = [node.target]
        if any(isinstance(target, ast.Name) and target.id == variable for target in targets):
            return True
    return False


def hole_probe_source(source: str, variable: str = TALLY_VARIABLE) -> str | None:
    """Rewrite a scoring function so it returns its own hole tally.

    The question "did the revision fix the hole count, or replace it with a
    different wrong one?" cannot be answered by looking for a string in the
    source. It can be answered by asking the function what it counts and
    comparing that with what the engine counts.

    Getting at a local variable would normally mean tracing the function as it
    runs, which would mean executing model-written code in this process -- the
    one thing `CLAUDE.md` forbids outright. So the value is surfaced instead:
    swap the final `return <weighted sum>` for `return float(holes)`, and the
    rewritten function is still ordinary source that goes through the AST
    allowlist and runs in the sandbox like any other.

    Returns None when the rewrite cannot be done unambiguously -- no `score`, no
    variable of that name, or more than one `return`, where which branch a given
    board takes is not knowable from the text. A probe that might be reading the
    wrong thing is worse than no probe, so this says so rather than guessing.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    definition = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == FUNCTION_NAME
        ),
        None,
    )
    if definition is None or not _assigns(definition, variable):
        return None

    returns = [node for node in ast.walk(definition) if isinstance(node, ast.Return)]
    if len(returns) != 1 or definition.body[-1] is not returns[0]:
        return None

    definition.body[-1] = ast.Return(
        value=ast.Call(
            func=ast.Name(id="float", ctx=ast.Load()),
            args=[ast.Name(id=variable, ctx=ast.Load())],
            keywords=[],
        )
    )
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"


@dataclass(frozen=True)
class ProbeRow:
    """What the engine counts on one board, and what the function counts."""

    label: str
    truth: int
    #: None when the function raised or timed out on this board.
    reported: float | None

    @property
    def agrees(self) -> bool:
        return self.reported is not None and self.reported == float(self.truth)


def probe_hole_tally(source: str, boards: list[tuple[str, Board]]) -> list[ProbeRow] | None:
    """Ask a function what it counts as holes, on boards the engine has measured.

    None means the function could not be probed (see :func:`hole_probe_source`);
    an empty list means there were no boards to probe.
    """
    probe = hole_probe_source(source)
    if probe is None:
        return None

    items = [
        {"board": [list(row) for row in board.occupancy()], "placement": dict(PROBE_PLACEMENT)}
        for _, board in boards
    ]
    if not items:
        return []
    with ScoringSandbox(probe) as sandbox:
        values = sandbox.score(items)
    return [
        ProbeRow(label=label, truth=holes(board), reported=None if value == UNPLAYABLE else value)
        for (label, board), value in zip(boards, values, strict=True)
    ]


def format_probe(rows: list[ProbeRow] | None) -> str:
    """The hole-count comparison as a few indented lines."""
    if rows is None:
        return (
            f"         hole count: NOT PROBED (no single final return, or no "
            f"{TALLY_VARIABLE!r} variable)"
        )
    if not rows:
        return "         hole count: NOT PROBED (no boards)"

    parts = []
    for row in rows:
        reported = "raised/timed out" if row.reported is None else f"{row.reported:.0f}"
        parts.append(f"{row.label}: engine {row.truth}, function {reported}")
    agree = sum(1 for row in rows if row.agrees)
    verdict = "CORRECT" if agree == len(rows) else f"WRONG on {len(rows) - agree}/{len(rows)}"
    return "         hole count: " + verdict + "\n" + "\n".join(f"           - {p}" for p in parts)


def report_prompt_lengths(control: str, counterexample: str, null: str, first: str) -> None:
    """Print the four prompt lengths, and the asymmetry, without softening it.

    The counterexample arm's claim that "prompt length cannot explain the result"
    rests on being 142 characters from the control. This arm's null is further
    away than that and cannot be brought closer without adding content that is
    itself a treatment, so the gap is printed rather than padded.
    """
    base = len(control)
    print("prompt lengths (chars)")
    for label, prompt in (
        ("iteration 0 (no previous function)", first),
        ("null (this arm)", null),
        ("control (outcome feedback)", control),
        ("counterexample (outcome + trace)", counterexample),
    ):
        delta = len(prompt) - base
        against = "" if delta == 0 else f"   control {delta:+5d}  ({delta / base:+.1%})"
        print(f"  {label:36} {len(prompt):5d}{against}")

    declaration = MEASUREMENT_DECLARATION.strip()
    print()
    if declaration in control and declaration not in counterexample:
        # Guards against a regression of the defect described below.
        print(
            f"  WARNING: the counterexample prompt is missing the {len(declaration)}-char\n"
            "  measurement declaration that the control carries, so its difference from the\n"
            "  control is two blocks (one removed, one added) rather than one added. Its net\n"
            "  length understates how much text differs. See f840a10 for why that block\n"
            "  exists at all. This arm's null keeps the declaration, as the control does."
        )
    else:
        print(
            "  All three prompts carry the measurement declaration, so each arm differs\n"
            "  from the control in exactly one block: the null removes the outcome summary,\n"
            "  the counterexample inserts a trace block. Note that the recorded\n"
            "  counterexample runs (held-out 2,540 / 120 / 5) predate that fix and were\n"
            "  generated from a prompt that also dropped the declaration."
        )
    print()
    # The deviations are roughly equal and opposite -- the null removes ~708
    # chars of outcome data, the counterexample adds ~560 chars of trace data --
    # which is the shape a three-point axis wants. It is worth printing because
    # the alternative `withheld` variant sits at only -176 and would make the
    # ladder lopsided, not more comparable. See `withheld_feedback_section`.
    print(
        f"  deviation from the control: null {len(null) - base:+d}, "
        f"counterexample {len(counterexample) - base:+d}"
    )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3-14b")
    parser.add_argument("--config", type=Path, default=Path("configs/models.yaml"))
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="generations to take. Three, not one: varying the counterexample's board gave"
        " held-out 2540/120/5 from nominally equivalent prompts, so one sample of a"
        " no-feedback baseline would establish nothing",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        default=1,
        help="first artifact number; raise it so a replication does not overwrite earlier runs",
    )
    parser.add_argument(
        "--variant",
        choices=("bare", "withheld"),
        default="bare",
        help="bare: the outcome block is removed. withheld: its headings and labels stay with"
        " every value replaced, which holds the prompt's shape but tells the model that"
        " measurements are being kept from it",
    )
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--probe-at",
        type=int,
        nargs="+",
        default=[8, 16, 24],
        help="piece counts whose boards the hole-count probe uses. The default three are the"
        " boards the counterexample arm's variants were run on",
    )
    parser.add_argument("--max-pieces", type=int, default=500)
    parser.add_argument("--function", type=Path, default=None, help="the function to revise")
    parser.add_argument(
        "--timeout",
        type=float,
        default=2400.0,
        help="per-call budget; the control's revisions took 476-488s and the counterexample's"
        " 841s, so this is generous on purpose",
    )
    args = parser.parse_args()

    # Retries are disabled deliberately. A local generation that exceeds its
    # budget will exceed it again, and the counterexample arm's first attempt
    # spent 60 of its 80 minutes on three pointless retries after a timeout.
    config = replace(
        load_model_config(args.config, args.model),
        timeout_seconds=args.timeout,
        max_retries=0,
    )
    loop_config = LoopConfig(
        model=config.name, train_seeds=(args.seed,), max_pieces=args.max_pieces
    )
    path = args.function or Path(f"runs/functions/noise/{config.name}-noise1.py")
    if not path.exists():
        raise SystemExit(f"no previous function at {path}; pass --function")
    source = path.read_text()

    # The outcome is still computed, even though the null prompt reports none of
    # it: `previous.source` is what the model is shown, and the control and
    # counterexample prompts printed below need the real summary to be the real
    # thing rather than a fabrication.
    previous = play_function(source, args.seed, loop_config)
    base = held_out(source, args.max_pieces)
    print(f"model {config.name} ({config.model})")
    print(f"revising {path}  (variant: {args.variant})")
    print(
        f"iteration 0 held-out over {len(HELD_OUT_SEEDS)} unseen seeds: "
        f"score {base[0]:.0f} pieces {base[1]:.1f} holes {base[2]:.1f}\n",
        flush=True,
    )

    # Two replays of a game that ends in well under a second. Separate calls
    # because the probe wants several structurally different boards while the
    # length comparison wants the single board the counterexample arm really ran.
    probe_boards = sample_boards(source, args.seed, loop_config, at=tuple(args.probe_at))
    comparison_boards = sample_boards(source, args.seed, loop_config, at=(COMPARISON_PIECE,))

    null = build_null_prompt(loop_config, previous, args.variant)
    report_prompt_lengths(
        control=build_prompt(loop_config, previous),
        counterexample=build_counterexample_prompt(loop_config, previous, comparison_boards),
        null=null,
        first=build_prompt(loop_config, None),
    )

    # Probe the function being revised first. It is known to miscount, so this is
    # the instrument's own control: a probe that called the broken function
    # correct would not be worth reading afterwards.
    print("hole-count probe on the function being revised (known to be wrong):")
    print(format_probe(probe_hole_tally(source, probe_boards)), flush=True)
    print()

    out_dir = Path("runs/functions/null")
    out_dir.mkdir(parents=True, exist_ok=True)

    for index in range(args.start_index, args.start_index + args.runs):
        client = ModelClient(config)
        started = time.monotonic()
        response = client.complete([{"role": "user", "content": null}])
        elapsed = time.monotonic() - started
        try:
            generated = extract_code(response.text)
        except Exception as error:  # noqa: BLE001 - an unparseable reply is a result
            print(f"run {index}: UNPARSEABLE ({error})", flush=True)
            continue

        (out_dir / f"{config.name}-null-{args.variant}-{index}.py").write_text(generated)
        digest = hashlib.sha256(generated.encode()).hexdigest()[:12]
        score, pieces, hole_count = held_out(generated, args.max_pieces)
        print(
            # Generation length is reported because it is the empirical answer to
            # the objection this arm cannot design away: if a shorter prompt had
            # produced a shorter, shallower generation, that would be visible
            # here. The control's revisions ran 6,002 and 5,611 output tokens on
            # roughly 23,000 characters of reasoning.
            f"run {index}: {digest}  {elapsed:.0f}s  out={client.usage.tokens_out} "
            f"reasoning={len(response.reasoning)} chars\n"
            f"         held-out: score {score:.0f} pieces {pieces:.1f} holes {hole_count:.1f}\n"
            f"{format_probe(probe_hole_tally(generated, probe_boards))}",
            flush=True,
        )

    print()
    print("ALREADY COLLECTED, for comparison (held-out means over the same 20 seeds):")
    print("  iteration 0, the function being revised            110    the bug it starts with")
    print("  control A / B, outcome feedback                 130 / 85  bug untouched in both")
    print("  counterexample, trace board after 16 pieces        2540   hole count fixed (x2)")
    print("  counterexample, trace board after 24 pieces         120   bug untouched")
    print("  counterexample, trace board after  8 pieces           5   a different, worse bug")
    print("  reference heuristic                              20915")
    print()
    print("Read this arm against that spread, not against 2,540 alone. Three prompts")
    print("differing only in which board they showed produced 2540 / 120 / 5, so what")
    print("a no-feedback baseline has to establish is a *distribution*, not a point.")


if __name__ == "__main__":
    main()
