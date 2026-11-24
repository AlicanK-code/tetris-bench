"""What separates a reweighting that gains from one that collapses?

Two revisions in this corpus moved their weights the same qualitative direction
-- hole penalty up, line reward down, "survive, do not chase lines" -- and ended
in opposite places. `qwen3-30b` chain 1 went 41.55 to 50.19 points per piece,
the best function the project has; `qwen3-8b` chain 3 went 34.57 to 11.46, the
worst collapse in its run. The 30B write-up credited the direction, which this
module exists to test, because a direction that produces both outcomes explains
neither.

The method is a **term-level replay**: hold a function's structure fixed, change
only its numeric weights, and replay it on the held-out seeds. Each function is
then its own baseline, so nothing depends on the four rungs computing their
terms the same way -- which they do not. Two designs are used.

**A factorial**, where a revision changed more than its weights. The 30B's
iteration 0 computed its column heights by scanning *up* from row 19 and
stopping at the first filled cell, which on any column resting on the floor
yields ``19 - 19 = 0``: its height and bumpiness terms were dead, and the
capability probes recorded it as ``height: blind``. Iteration 5 scans down from
row 0 and is correct. So that revision repaired two terms *and* reweighted, and
the two can be crossed to measure each.

**A one-at-a-time ablation**, where only the weights changed. Walking each
weight individually from its old value to its new one says which term carried
the outcome, which a single before-and-after number cannot.

Both are cheap -- a saved function replays in well under a second -- and neither
needs a model.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from tetris_bench.engine.game import Game
from tetris_bench.engine.placements import Placement
from tetris_bench.placement_diff import choose_index
from tetris_bench.sandbox import ScoringSandbox, build_items


@dataclass(frozen=True)
class Factorial:
    """A 2x2 design: two binary factors, one measured outcome in each cell.

    Named ``low``/``high`` rather than after any particular experiment so the
    arithmetic can be tested without reference to boards or weights.
    """

    low_low: float
    high_low: float
    low_high: float
    high_high: float

    @property
    def effect_a(self) -> float:
        """Factor A alone, with B held at its low level."""
        return self.high_low - self.low_low

    @property
    def effect_b(self) -> float:
        """Factor B alone, with A held at its low level."""
        return self.low_high - self.low_low

    @property
    def total(self) -> float:
        """Both factors together -- what the revision actually did."""
        return self.high_high - self.low_low

    @property
    def interaction(self) -> float:
        """How much the two factors are worth together beyond their sum.

        A large positive interaction means neither factor explains the outcome
        on its own: the revision worked because it did both things at once.
        """
        return self.high_high - self.high_low - self.low_high + self.low_low


@dataclass(frozen=True)
class Ablation:
    """One weight moved from a baseline value to a target value."""

    term: str
    index: int
    frm: float
    to: float
    rate: float
    baseline: float

    @property
    def delta(self) -> float:
        return self.rate - self.baseline


def ablation_weights(
    baseline: Sequence[float], target: Sequence[float]
) -> list[tuple[str | None, tuple[float, ...]]]:
    """The baseline, then one variant per weight moved to its target value.

    Returned as ``(term index or None, weights)`` pairs with the untouched
    baseline first, so a caller replays them in order and attributes each
    measured difference to exactly one weight. A weight whose target equals its
    baseline is still included: "moving it changes nothing" is a result, and
    silently dropping it would make the table disagree with the function.
    """
    if len(baseline) != len(target):
        raise ValueError(f"weight vectors differ in length: {len(baseline)} vs {len(target)}")
    variants: list[tuple[str | None, tuple[float, ...]]] = [(None, tuple(baseline))]
    for index in range(len(baseline)):
        weights = list(baseline)
        weights[index] = target[index]
        variants.append((str(index), tuple(weights)))
    return variants


def render(template: str, weights: Sequence[float]) -> str:
    """Fill a source template's ``%g`` slots with a weight vector.

    ``%g`` rather than ``%f`` on purpose: a weight of ``0.5`` must render as
    ``0.5`` and one of ``100`` as ``100``, because these sources are published as
    artifacts and a reader compares them against the model's original by eye.
    """
    if template.count("%g") != len(weights):
        raise ValueError(f"template has {template.count('%g')} slots for {len(weights)} weights")
    return template % tuple(weights)


@dataclass
class TieCounts:
    """How often the maximum was shared, and by how many candidates."""

    moves: int = 0
    tied_moves: int = 0
    tied_total: int = 0
    largest: int = 0

    @property
    def tied_share(self) -> float:
        """Share of decisions where something other than the terms decided."""
        return self.tied_moves / self.moves if self.moves else 0.0

    @property
    def mean_size(self) -> float:
        return self.tied_total / self.moves if self.moves else 0.0


class TieCountingAgent:
    """Plays the first maximum, recording how many candidates tied with it.

    This exists because :class:`StrategyDiagnostics` counts *flat* moves -- ones
    where every candidate scored alike -- and that is the wrong diagnostic for a
    tie-breaker. A function can separate its candidates well overall while still
    leaving a large set tied at the top, and it is only that top set a
    tie-breaker ever chooses among. Measured on the 30B's broken function, flat
    moves are 2% while moves with a tie at the maximum are 47%.

    The choice rule is :func:`tetris_bench.placement_diff.choose_index`, the same
    first-maximum rule :class:`StrategyAgent` uses, so the scores this agent
    produces are the scores that agent would have produced.
    """

    def __init__(self, sandbox: ScoringSandbox) -> None:
        self.name = "tie-counting"
        self.sandbox = sandbox
        self.ties = TieCounts()

    def choose(self, game: Game) -> Placement:
        placements = game.legal_placements()
        if not placements:
            raise ValueError("no legal placements: the game is over and should not be stepped")
        scores = self.sandbox.score(build_items(game.board, placements))
        best = max(scores)
        shared = sum(1 for value in scores if value == best)

        self.ties.moves += 1
        self.ties.tied_total += shared
        self.ties.largest = max(self.ties.largest, shared)
        if shared > 1:
            self.ties.tied_moves += 1
        return placements[choose_index(scores)]
