"""How large a gain a loop run could have detected.

Every null in this project is a *bounded* null -- "no change larger than X" --
and X is the minimum detectable gain. That arithmetic has been written inline in
four documents and three scripts, which is how the repo came to publish a ratio
computed against two different denominators. It lives here now, with the
published figures pinned in ``tests/test_power.py``.

The quantity being tested is a **paired** one: each chain's own first-to-last
difference, since chains are independent lineages and a chain is its own
control. So the relevant spread is the standard deviation of those differences,
:attr:`RungPower.paired_sd`, and **not** the spread between chains at a single
iteration. The two are reported side by side because the project spent a week
assuming one could be scaled from the other, and
[`30b-loop-is-underpowered-not-futile.md`](../../docs/findings/30b-loop-is-underpowered-not-futile.md)
records how that ended: the ratio runs 0.70x, 0.84x, 1.07x and 2.39x across the
four rungs, so there is nothing to scale by.
"""

from __future__ import annotations

import collections
import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

#: ``z(1 - alpha/2) + z(power)`` at 80% power and alpha = 0.05 two-sided:
#: 1.960 + 0.842, rounded. The conventional constant for a paired comparison,
#: used throughout this repo so that one run's "detectable" means another's.
MDE_CONSTANT = 2.8


def minimum_detectable(paired_sd: float, chains: int) -> float:
    """The smallest mean gain ``chains`` chains could resolve.

    A normal approximation, which is the right call here only because the
    quantity is a mean of per-chain differences rather than a count; the
    discrete tests in :mod:`tetris_bench.zeros_rate` are simulated instead,
    for exactly the reason this one is not.
    """
    if chains <= 0:
        raise ValueError("a run has at least one chain")
    return MDE_CONSTANT * paired_sd / math.sqrt(chains)


def chains_for(paired_sd: float, target: float) -> int:
    """Chains needed to resolve a gain of ``target``, rounded up.

    ``target`` is taken as a magnitude: asking how many chains would resolve a
    *fall* of 5 is the same question as for a rise of 5.

    **Quote these to two significant figures.** The count goes as the square of
    an estimated standard deviation, so it is far more precise-looking than it
    is: feeding this the 8B's figures rounded to two decimals gives 193 chains
    and feeding it the unrounded ones gives 194. Figures published in this repo
    before 2026-11-24 were rounded to nearest rather than up, so a comparison
    against them can differ by one.
    """
    if target == 0:
        raise ValueError("no sample size resolves a gain of zero")
    return math.ceil((MDE_CONSTANT * paired_sd / abs(target)) ** 2)


@dataclass(frozen=True)
class RungPower:
    """What one loop run measured, and what it could have measured."""

    model: str
    chains: int
    median_gain: float
    paired_sd: float
    chain_spread: float

    @property
    def mde(self) -> float:
        return minimum_detectable(self.paired_sd, self.chains)

    @property
    def ratio(self) -> float:
        """Paired spread over between-chain spread. No constant across rungs."""
        return self.paired_sd / self.chain_spread if self.chain_spread else math.nan

    @property
    def detected(self) -> bool:
        """Did the observed gain clear the bar? Not once, on any rung."""
        return abs(self.median_gain) >= self.mde

    def chains_for_observed(self) -> int | None:
        """Chains that would have resolved the gain this run actually saw."""
        if self.median_gain == 0:
            return None
        return chains_for(self.paired_sd, self.median_gain)


def held_out_rates(rows: Sequence[dict]) -> dict[tuple[int, int], float]:
    """Points per piece per position, from the evaluation split only.

    Totals over totals, which is what the headline rate is everywhere else in
    the project: a mean of per-game rates would weight a 40-piece game as
    heavily as a 2,000-piece one.
    """
    totals: dict[tuple[int, int], list[int]] = collections.defaultdict(lambda: [0, 0])
    for row in rows:
        if row.get("split") == "eval":
            key = (row["chain"], row["iteration"])
            totals[key][0] += row["score"]
            totals[key][1] += row["pieces_placed"]
    return {key: score / pieces for key, (score, pieces) in totals.items() if pieces}


def summarise(rows: Sequence[dict], chain_spread: float) -> RungPower:
    """Reduce one loop log to its power summary.

    A chain's gain is its **last measured position minus its first**, not
    ``iteration 5 - iteration 0``: a rejected generation plays no games, so a
    chain can start at iteration 1 or end at iteration 4, and treating a missing
    position as a zero would turn a rejection into a collapse.

    ``chain_spread`` is passed in rather than computed because it comes from
    :meth:`tetris_bench.curves.Curve.chain_spread`, and recomputing it here is
    how the repo ended up with two definitions of one denominator.
    """
    rates = held_out_rates(rows)
    if not rates:
        raise ValueError("no held-out games in this log, so there is no curve")

    by_chain: dict[int, list[int]] = collections.defaultdict(list)
    for chain, iteration in rates:
        by_chain[chain].append(iteration)

    gains = []
    for chain, iterations in sorted(by_chain.items()):
        ordered = sorted(iterations)
        gains.append(rates[(chain, ordered[-1])] - rates[(chain, ordered[0])])
    if len(gains) < 2:
        raise ValueError("a paired standard deviation needs at least two chains")

    return RungPower(
        model=rows[0]["model"],
        chains=len(gains),
        median_gain=statistics.median(gains),
        paired_sd=statistics.stdev(gains),
        chain_spread=chain_spread,
    )
