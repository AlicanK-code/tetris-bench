"""Does the loop change how often a chain is *dead* rather than merely weak?

Four separate write-ups reached the same suspicion and none tested it: if the
loop's value is **rescuing functions that score nothing** rather than improving
ones that already work, the effect is a change in a *proportion*, and a mean is
the wrong instrument. ``curves.py`` compares medians, which cannot see it.

This module makes that proportion measurable, and the measurement needs two
things the mean version does not.

**A definition of "dead" that is not a round number.** Exactly 0.0 is too
strict -- a function whose every call crashes still accrues a little score from
the fallback placement, so it lands near but not at zero -- and "under 1.0" is
arbitrary. The line used here is empirical: the 95th percentile of what *random
play* scores over a 10-game evaluation, which is the same evaluation a loop
position gets. A function at or below it has not been shown to beat picking
arbitrarily. See :data:`RANDOM_CEILING`.

**A paired test.** Chains are not independent samples of one population; each
iteration is compared against *its own* previous iteration, so the evidence is
the discordant pairs — the positions that changed state — and the test is a
sign test on those. An unpaired proportion test would treat 10 positions from
2 chains as 10 independent draws and overstate its confidence.

Pure and unit-tested. Presentation lives in ``analysis/zeros_rate.py``.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from math import comb

RANDOM_CEILING = 0.851
"""Points per piece at the 95th percentile of random play's own 10-game rate.

Measured on the evaluation split (seeds 1000-1009) at the 2,000-piece budget,
over 20 agent seeds: random averages 0.327 points per piece overall, and a
single 10-game evaluation of it ranges 0.000 to 1.163 with this 95th
percentile. So a position at or below this is inside the range random reaches by
chance on the same number of games, and calling it "dead" is a measurement
rather than a judgement.

Reproduce it with ``analysis/zeros_rate.py --measure-floor``.
"""


@dataclass(frozen=True)
class Transitions:
    """Paired state changes within chains, and the sign test on them."""

    revivals: int
    deaths: int

    @property
    def discordant(self) -> int:
        """Pairs that changed state. The only pairs a sign test can use."""
        return self.revivals + self.deaths

    @property
    def p_value(self) -> float:
        """Two-sided exact sign test against "revival and death are equally likely".

        1.0 when nothing changed state, which is the honest answer: no
        discordant pairs is no evidence either way, not evidence of no effect.
        """
        return sign_test(self.revivals, self.discordant)


def is_dead(rate: float, ceiling: float = RANDOM_CEILING) -> bool:
    """Whether a position's held-out rate is inside random play's own range."""
    return rate <= ceiling


def count_transitions(series: list[list[float]], ceiling: float = RANDOM_CEILING) -> Transitions:
    """Count revivals and deaths across adjacent iterations, within each chain.

    ``series`` is one list of per-iteration rates per chain. Pairs are adjacent
    iterations of the same chain, never across chains, because a chain is the
    only thing the loop actually carries forward.
    """
    revivals = deaths = 0
    for chain in series:
        # strict=False is correct, not a shortcut: the sequences are
        # deliberately of different length, offset by one.
        for before, after in zip(chain, chain[1:], strict=False):
            if is_dead(before, ceiling) and not is_dead(after, ceiling):
                revivals += 1
            elif not is_dead(before, ceiling) and is_dead(after, ceiling):
                deaths += 1
    return Transitions(revivals=revivals, deaths=deaths)


def sign_test(successes: int, trials: int) -> float:
    """Two-sided exact binomial test against p = 0.5.

    Summing every outcome at most as likely as the observed one, which is the
    conventional two-sided exact p and is exact rather than a normal
    approximation -- necessary here, where `trials` is single digits.
    """
    if trials == 0:
        return 1.0
    weights = [comb(trials, k) / 2**trials for k in range(trials + 1)]
    observed = weights[successes]
    return min(1.0, sum(w for w in weights if w <= observed + 1e-12))


def chains_needed(
    pair_discordance: float,
    revival_share: float,
    *,
    pairs_per_chain: int = 5,
    power: float = 0.80,
    alpha: float = 0.05,
    trials: int = 4000,
    limit: int = 1000,
    seed: int = 0,
) -> int | None:
    """Chains required for the sign test to reach ``power``, by simulation.

    Simulated rather than derived because the test is exact and discrete, so a
    normal-approximation formula is wrong at these sizes in a direction that
    flatters the experiment.

    A chain of ``iterations`` positions contributes ``pairs_per_chain`` adjacent
    pairs, each of which changes state with probability ``pair_discordance``.
    ``revival_share`` is the chance a changed pair is a revival under the
    alternative; 0.5 is the null, at which no sample size suffices and this
    returns ``None``.

    Note that the binding resource is **discordant pairs, not chains**. A loop
    whose chains rarely change state is harder to judge however long it runs,
    which is why ``pair_discordance`` is a parameter and not a constant.
    """
    rng = random.Random(seed)
    for n in range(5, limit + 1, 5):
        hits = 0
        for _ in range(trials):
            changed = sum(rng.random() < pair_discordance for _ in range(n * pairs_per_chain))
            revived = sum(rng.random() < revival_share for _ in range(changed))
            if sign_test(revived, changed) < alpha:
                hits += 1
        if hits / trials >= power:
            return n
    return None
