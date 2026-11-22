"""Print which generated functions can express a strategy at all.

The classification itself lives in :mod:`tetris_bench.term_diagnostics`, which
is pure and unit-tested; this file is only presentation, so a change to how a
verdict is displayed can never change the verdict.

Read the `strategy-capable` fraction as a capability measure in its own right,
separate from score. A function that fails these probes is not playing badly --
it is incapable of playing, because a term it relies on is inverted or
identically zero. Reporting one number that mixes the two is what let a plateau
at ~1,000 points look like a strategy ceiling when it was four dead terms.

    uv run python analysis/term_diagnostics.py runs/functions
    uv run python analysis/term_diagnostics.py runs/functions/ladder --flip
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tetris_bench.term_diagnostics import (
    OK,
    classify,
    flipped_probes,
    probes,
    sources,
)


def report(directory: Path, with_flip: bool = False) -> str:
    """Classify every function in a directory and summarise the result."""
    names = [probe.name for probe in probes()]
    flip_pairs = flipped_probes() if with_flip else None

    header = f"{'function':>34} " + " ".join(f"{name:>10}" for name in names)
    if with_flip:
        header += f"  {'upside down?':>13}"
    lines = [header, "-" * len(header)]

    verdicts = []
    for label, source in sources(directory):
        verdict = classify(source, label)
        verdicts.append(verdict)
        row = f"{label:>34} " + " ".join(f"{verdict.answers[n]:>10}" for n in names)
        if with_flip:
            # Inlined rather than calling `is_upside_down`, which would classify
            # upright a second time; the verdict is already in hand.
            flipped = classify(source, label, flip_pairs)
            upside_down = not verdict.strategy_capable and flipped.strategy_capable
            row += f"  {'yes' if upside_down else '':>13}"
        lines.append(row)

    if not verdicts:
        return f"no functions found in {directory}"

    capable = sum(1 for v in verdicts if v.strategy_capable)
    lines += [
        "",
        f"strategy-capable: {capable}/{len(verdicts)} ({capable / len(verdicts):.0%})",
        "",
        "A function is strategy-capable when it answers every probe above",
        "correctly. The probes are not strategy questions -- a 3-deep board",
        "really is better than a 12-deep one -- so a failure is a defect, and",
        "the score of a function that fails says nothing about its strategy.",
    ]
    for name in names:
        wrong = sum(1 for v in verdicts if v.answers[name] != OK)
        if wrong:
            diagnosis = next(p.diagnosis for p in probes() if p.name == name)
            lines.append(f"  {name}: {wrong}/{len(verdicts)} -- {diagnosis}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?", default=Path("runs/functions"))
    parser.add_argument(
        "--flip",
        action="store_true",
        help="also test every board upside down, to separate a sign error from confusion",
    )
    args = parser.parse_args()
    print(report(args.directory, with_flip=args.flip))


if __name__ == "__main__":
    main()
