"""Can a generated function express a strategy at all?

A score alone cannot distinguish a bad strategy from arithmetic that is
structurally incapable of being one. Two failure modes produce the same low
number, and the first five-chain sweep was full of both:

**Inverted.** The function prefers the worse board. Ten of thirty functions on
the 14B rung preferred a 12-deep stack to a 3-deep one, because they counted the
empty space *above* the stack and called it holes. `board` has row 0 at the top,
so this is a sign error dressed as a measurement.

**Dead.** The function computes a term that is identically zero on every board,
so it cannot contribute to a choice however it is weighted. The common shape::

    for row in range(20):        # from the TOP
        if board[row][col]: h += 1
        else: break              # row 0 is empty, so this breaks immediately

`heights` is `[0] * 10` forever, which silently kills every term built on it --
bumpiness, aggregate height, sum of squares. Those chains then spent five
revisions tuning weights on quantities that could never change. The prompt warns
about exactly this ("check that each term you use actually *varies*"), so the
failure is the model's; the point here is that the *benchmark* could not see it.

This module makes the distinction measurable: each probe is a pair of boards
where the better one is not a matter of strategy, so a function that prefers the
worse one, or scores them identically, is reporting a defect rather than an
opinion. A function is :attr:`Verdict.strategy_capable` when it answers every
probe correctly.

Nothing here is fed back to a model. Telling a model its height term is dead
would hand it the diagnosis, and self-diagnosis is the ability the benchmark
exists to measure. This is instrumentation for the analysis, not feedback.

Presentation lives in ``analysis/term_diagnostics.py``; everything here is pure
and unit-tested, so a change to how a verdict is displayed cannot change it.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from tetris_bench.engine.board import DEFAULT_HEIGHT, DEFAULT_WIDTH
from tetris_bench.sandbox import ScoringSandbox

#: Verdicts. `BLIND` and `INVERTED` stay apart because they are different
#: defects: arithmetic that cannot vary, versus a sign error.
OK, BLIND, INVERTED, FAILED = "ok", "blind", "INVERTED", "failed"


def blank() -> list[list[bool]]:
    return [[False] * DEFAULT_WIDTH for _ in range(DEFAULT_HEIGHT)]


def flat(rows_filled: int) -> list[list[bool]]:
    """A hole-free flat surface `rows_filled` deep, with one notch.

    The notch in the last column keeps every row incomplete, so no probe board
    is one that a line clear would already have removed.
    """
    board = blank()
    for row in range(DEFAULT_HEIGHT - rows_filled, DEFAULT_HEIGHT):
        for col in range(DEFAULT_WIDTH):
            board[row][col] = True
        board[row][DEFAULT_WIDTH - 1] = False
    return board


def flip(board: list[list[bool]]) -> list[list[bool]]:
    """The same board upside down, for telling a sign error from confusion."""
    return [list(row) for row in reversed(board)]


def item(board: list[list[bool]], lines: int = 0) -> dict:
    """Wrap a board as the sandbox's scoring item.

    The placement is identical for both halves of every pair, so a function that
    reads only `placement` and ignores `board` answers `blind` everywhere --
    which is the correct verdict for it.
    """
    return {
        "board": [list(row) for row in board],
        "placement": {
            "kind": "O",
            "rotation": 0,
            "column": 0,
            "row": 0,
            "cells": [[0, 0], [0, 1], [1, 0], [1, 1]],
            "lines_cleared": lines,
        },
    }


@dataclass(frozen=True)
class Probe:
    """A pair of boards whose ranking is not a matter of opinion."""

    name: str
    better: dict
    worse: dict
    #: What a wrong answer tells you about the function.
    diagnosis: str


def probes() -> list[Probe]:
    """The pairs. Each is deliberately crude: no strategy is being judged."""
    holed = flat(6)
    holed[17][3] = False  # bury a hole three rows down
    holed[13][3] = True  # and put the cell back on top, so the cell count matches

    shallow = blank()
    for row in (17, 18, 19):
        shallow[row][0] = True
    above_gap = [list(row) for row in shallow]
    for row in (10, 11, 12, 13, 14, 15):
        above_gap[row][0] = True  # six more cells, ten rows up, gap at row 16

    return [
        Probe(
            "height",
            item(flat(3)),
            item(flat(12)),
            "prefers a taller stack, or cannot see height at all",
        ),
        Probe(
            "holes",
            item(flat(6)),
            item(holed),
            "prefers a buried hole to a clean surface",
        ),
        Probe(
            "above-gap",
            item(shallow),
            item(above_gap),
            "blind to everything stacked above the first gap",
        ),
        Probe(
            "lines",
            item(flat(5), lines=2),
            item(flat(5), lines=0),
            "does not prefer clearing rows",
        ),
    ]


def flipped_probes() -> list[Probe]:
    """The same probes with every board upside down.

    A function that is wrong upright and right here was correct code pointed the
    wrong way up -- it believed row 0 was the floor. One that is wrong both ways
    is confused about something else. A correct function MUST invert here, which
    is the control that keeps this test honest.
    """
    return [
        Probe(
            probe.name,
            item(flip(probe.better["board"]), probe.better["placement"]["lines_cleared"]),
            item(flip(probe.worse["board"]), probe.worse["placement"]["lines_cleared"]),
            probe.diagnosis,
        )
        for probe in probes()
    ]


@dataclass(frozen=True)
class Verdict:
    """How one function answered the probes."""

    label: str
    answers: dict[str, str]

    @property
    def strategy_capable(self) -> bool:
        """Whether every term the probes test is present and correctly signed.

        The bar is deliberately low -- these are not strategy questions -- so a
        function that fails is not weak, it is broken, and its score says
        nothing about the strategy it was trying to express.
        """
        return all(answer == OK for answer in self.answers.values())

    @property
    def broken_terms(self) -> list[str]:
        return [name for name, answer in self.answers.items() if answer != OK]


def judge(better: float, worse: float) -> str:
    """Turn a pair of scores into a verdict."""
    if better == worse:
        return BLIND
    return OK if better > worse else INVERTED


def classify(source: str, label: str, pairs: list[Probe] | None = None) -> Verdict:
    """Run one function against every probe, inside the sandbox.

    Sandboxed for the same reason the games are: this is model-written code, and
    having already run it once does not make it trusted. A function that will
    not load is recorded as `failed` rather than raising, because "it does not
    even load" is a datum about that function, not an error in this analysis.
    """
    pairs = pairs if pairs is not None else probes()
    items = [half for probe in pairs for half in (probe.better, probe.worse)]
    try:
        with ScoringSandbox(source) as box:
            scores = box.score(items)
    except Exception:  # noqa: BLE001 - see the docstring
        return Verdict(label, {probe.name: FAILED for probe in pairs})
    return Verdict(
        label,
        {
            probe.name: judge(scores[2 * index], scores[2 * index + 1])
            for index, probe in enumerate(pairs)
        },
    )


def is_upside_down(source: str, label: str = "") -> bool:
    """Whether this function is a *correct* function with the board flipped.

    Strict on purpose: it fails every probe test upright and passes **all** of
    them flipped, which is the bar for claiming the code itself is right and
    only the convention is wrong. Nine of the twenty broken functions on the 14B
    rung answered this way.

    A function that is missing a term entirely will not qualify even when the
    term it does have is plainly bottom-origin -- it is not a correct function
    either way up. Use :func:`terms_that_flip` for that finer evidence.
    """
    if classify(source, label).strategy_capable:
        return False
    return classify(source, label, flipped_probes()).strategy_capable


def terms_that_flip(source: str, label: str = "") -> list[str]:
    """Which individual terms are wrong upright and right upside down.

    Weaker evidence than :func:`is_upside_down` and more sensitive: it catches
    the function whose height loop scans from row 0 downward -- correct only if
    row 0 were the floor -- even when the rest of the function is too thin to be
    correct in either orientation.
    """
    upright = classify(source, label).answers
    flipped = classify(source, label, flipped_probes()).answers
    return [name for name in upright if upright[name] != OK and flipped.get(name) == OK]


def sources(directory: Path | str) -> Iterator[tuple[str, str]]:
    """Yield (label, source) for every saved function, in a stable order."""
    for path in sorted(Path(directory).glob("*.py")):
        yield path.stem, path.read_text(encoding="utf-8")


def classify_directory(directory: Path | str) -> list[Verdict]:
    """Classify every saved function in a directory."""
    return [classify(source, label) for label, source in sources(directory)]
